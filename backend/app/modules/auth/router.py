import secrets
import string
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

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
