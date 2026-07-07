import secrets
import string
from datetime import UTC, datetime, timedelta
from typing import Annotated
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.config import get_settings
from app.database import get_db
from app.models import AccountLinkingCode, User
from app.models import UserPlatformAccount
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import (
    AccountLinkingCodeResponse,
    PlatformAccountResponse,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.modules.auth.security import create_access_token
from app.modules.auth.security import hash_password, verify_password


router = APIRouter(prefix="/auth", tags=["auth"])
LINKING_CODE_ALPHABET = string.ascii_uppercase + string.digits
LINKING_CODE_LENGTH = 6
AUTH_TOKEN_COOKIE = "sakoo_auth_token"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_STATE_COOKIE = "sakoo_google_oauth_state"
GOOGLE_NEXT_COOKIE = "sakoo_google_oauth_next"
GOOGLE_OAUTH_COOKIE_MAX_AGE_SECONDS = 10 * 60


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    payload: UserRegisterRequest,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    existing_user = db.scalar(select(User).where(User.email == payload.email))
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered",
        )

    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        phone_number=payload.phone_number,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User data already exists",
        ) from exc

    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login_user(
    payload: UserLoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenResponse(access_token=create_access_token(subject=str(user.id)))


@router.get("/google/start")
def start_google_login(
    next: str = "/",
) -> RedirectResponse:
    settings = get_settings()
    _require_google_oauth_config(settings)

    state = secrets.token_urlsafe(32)
    query = urlencode(
        {
            "client_id": settings.google_oauth_client_id,
            "redirect_uri": _google_redirect_uri(settings),
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "prompt": "select_account",
        }
    )
    response = RedirectResponse(
        f"{GOOGLE_AUTH_URL}?{query}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
    _set_oauth_cookie(
        response,
        GOOGLE_STATE_COOKIE,
        state,
        secure=_google_redirect_uri(settings).startswith("https://"),
    )
    _set_oauth_cookie(
        response,
        GOOGLE_NEXT_COOKIE,
        _safe_next_path(next),
        secure=_google_redirect_uri(settings).startswith("https://"),
    )
    return response


@router.get("/google/callback")
def finish_google_login(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google login failed: {error}",
        )

    expected_state = request.cookies.get(GOOGLE_STATE_COOKIE)
    if not state or not expected_state or not secrets.compare_digest(state, expected_state):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Google login state",
        )
    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Google authorization code",
        )

    settings = get_settings()
    _require_google_oauth_config(settings)
    profile = _fetch_google_profile(code, settings)
    user = _get_or_create_google_user(db, profile)
    access_token = create_access_token(subject=str(user.id))

    response = RedirectResponse(
        _frontend_redirect_url(settings, _safe_next_path(request.cookies.get(GOOGLE_NEXT_COOKIE))),
        status_code=status.HTTP_303_SEE_OTHER,
    )
    response.set_cookie(
        AUTH_TOKEN_COOKIE,
        access_token,
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
        samesite="lax",
        secure=settings.app_base_url.startswith("https://"),
    )
    response.delete_cookie(GOOGLE_STATE_COOKIE, path="/")
    response.delete_cookie(GOOGLE_NEXT_COOKIE, path="/")
    return response


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    return current_user


@router.get("/platform-accounts", response_model=list[PlatformAccountResponse])
def list_platform_accounts(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[UserPlatformAccount]:
    return list(
        db.scalars(
            select(UserPlatformAccount)
            .where(UserPlatformAccount.user_id == current_user.id)
            .order_by(UserPlatformAccount.platform)
        )
    )


@router.post(
    "/linking-codes",
    response_model=AccountLinkingCodeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_account_linking_code(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AccountLinkingCodeResponse:
    settings = get_settings()
    now = datetime.now(UTC)
    expired_at = now + timedelta(minutes=settings.account_linking_code_ttl_minutes)
    db.execute(
        update(AccountLinkingCode)
        .where(
            AccountLinkingCode.user_id == current_user.id,
            AccountLinkingCode.used_at.is_(None),
            AccountLinkingCode.expired_at > now,
        )
        .values(expired_at=now)
    )

    for _attempt in range(10):
        linking_code = AccountLinkingCode(
            user_id=current_user.id,
            code=_generate_linking_code(),
            expired_at=expired_at,
        )
        db.add(linking_code)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue

        db.refresh(linking_code)
        return AccountLinkingCodeResponse(
            id=linking_code.id,
            code=linking_code.code,
            command=f"hubungkan {linking_code.code}",
            expired_at=linking_code.expired_at,
            created_at=linking_code.created_at,
        )

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Failed to generate linking code. Please try again.",
    )


def _generate_linking_code() -> str:
    return "".join(
        secrets.choice(LINKING_CODE_ALPHABET) for _ in range(LINKING_CODE_LENGTH)
    )


def _require_google_oauth_config(settings: Settings) -> None:
    if not settings.google_oauth_client_id or not settings.google_oauth_client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google SSO is not configured",
        )


def _google_redirect_uri(settings: Settings) -> str:
    if settings.google_oauth_redirect_uri.strip():
        return settings.google_oauth_redirect_uri.strip()
    return f"{settings.app_base_url.rstrip('/')}{settings.api_prefix}/auth/google/callback"


def _set_oauth_cookie(
    response: RedirectResponse,
    name: str,
    value: str,
    *,
    secure: bool,
) -> None:
    response.set_cookie(
        name,
        value,
        max_age=GOOGLE_OAUTH_COOKIE_MAX_AGE_SECONDS,
        path="/",
        httponly=True,
        samesite="lax",
        secure=secure,
    )


def _fetch_google_profile(code: str, settings: Settings) -> dict[str, str]:
    try:
        token_response = httpx.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "redirect_uri": _google_redirect_uri(settings),
                "grant_type": "authorization_code",
            },
            timeout=10.0,
        )
        token_response.raise_for_status()
        token_payload = token_response.json()
        access_token = token_payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise ValueError("missing_access_token")

        profile_response = httpx.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10.0,
        )
        profile_response.raise_for_status()
        profile = profile_response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google account could not be verified",
        ) from exc

    email = str(profile.get("email") or "").strip().lower()
    email_verified = profile.get("email_verified") is True or str(
        profile.get("email_verified")
    ).lower() == "true"
    if not email or not email_verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google email is not verified",
        )

    return {
        "email": email,
        "name": str(profile.get("name") or email.split("@", 1)[0]).strip(),
    }


def _get_or_create_google_user(db: Session, profile: dict[str, str]) -> User:
    user = db.scalar(select(User).where(User.email == profile["email"]))
    if user is not None:
        return user

    user = User(
        name=profile["name"] or profile["email"].split("@", 1)[0],
        email=profile["email"],
        password_hash=hash_password(secrets.token_urlsafe(32)),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User data already exists",
        ) from exc

    db.refresh(user)
    return user


def _safe_next_path(value: str | None) -> str:
    return value if value and value.startswith("/") and not value.startswith("//") else "/"


def _frontend_redirect_url(settings: Settings, next_path: str) -> str:
    return f"{settings.app_base_url.rstrip('/')}{next_path}"
