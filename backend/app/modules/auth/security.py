import base64
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import json
from typing import Any

import bcrypt
from fastapi import HTTPException, status

from app.config import get_settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(subject: str) -> str:
    settings = get_settings()
    if settings.jwt_algorithm != "HS256":
        raise _server_config_error("JWT algorithm is not supported")
    if not settings.jwt_secret:
        raise _server_config_error("JWT_SECRET is not configured")

    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)
    header = {"alg": settings.jwt_algorithm, "typ": "JWT"}
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }

    signing_input = ".".join(
        [
            _base64url_encode_json(header),
            _base64url_encode_json(payload),
        ]
    )
    signature = _sign(signing_input, settings.jwt_secret)
    return f"{signing_input}.{signature}"


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    if settings.jwt_algorithm != "HS256":
        raise _server_config_error("JWT algorithm is not supported")
    if not settings.jwt_secret:
        raise _server_config_error("JWT_SECRET is not configured")

    try:
        encoded_header, encoded_payload, signature = token.split(".")
    except ValueError as exc:
        raise _invalid_token_error() from exc

    signing_input = f"{encoded_header}.{encoded_payload}"
    expected_signature = _sign(signing_input, settings.jwt_secret)
    if not hmac.compare_digest(signature, expected_signature):
        raise _invalid_token_error()

    header = _base64url_decode_json(encoded_header)
    if header.get("alg") != settings.jwt_algorithm:
        raise _invalid_token_error()

    payload = _base64url_decode_json(encoded_payload)
    expires_at = payload.get("exp")
    if not isinstance(expires_at, int) or expires_at <= int(datetime.now(UTC).timestamp()):
        raise _invalid_token_error()

    return payload


def _base64url_encode_json(value: dict[str, Any]) -> str:
    raw = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _base64url_decode_json(value: str) -> dict[str, Any]:
    try:
        padded = value + "=" * (-len(value) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
        parsed = json.loads(decoded)
    except (ValueError, json.JSONDecodeError) as exc:
        raise _invalid_token_error() from exc
    if not isinstance(parsed, dict):
        raise _invalid_token_error()
    return parsed


def _sign(signing_input: str, secret: str) -> str:
    digest = hmac.new(
        secret.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _invalid_token_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _server_config_error(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=detail,
    )
