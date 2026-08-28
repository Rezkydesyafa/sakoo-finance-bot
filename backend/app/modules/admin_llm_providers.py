from __future__ import annotations

import asyncio
from time import perf_counter
from typing import Annotated

import httpx
from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import AnyHttpUrl, BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import LlmProvider, User
from app.modules.auth.admin import is_admin_email
from app.modules.auth.dependencies import get_current_user

router = APIRouter(prefix="/admin/llm-providers", tags=["admin-llm-providers"])


class ProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    base_url: AnyHttpUrl
    api_key: str = Field(min_length=1, max_length=4096)
    model: str = Field(min_length=1, max_length=255)
    enabled: bool = True
    priority: int = Field(default=100, ge=0)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        return _validate_provider_base_url(value)


class ProviderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    base_url: AnyHttpUrl | None = None
    api_key: str | None = Field(default=None, min_length=1, max_length=4096)
    model: str | None = Field(default=None, min_length=1, max_length=255)
    enabled: bool | None = None
    priority: int | None = Field(default=None, ge=0)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: AnyHttpUrl | None) -> AnyHttpUrl | None:
        return _validate_provider_base_url(value) if value is not None else None


class ProviderResponse(BaseModel):
    id: int
    name: str
    base_url: str
    model: str
    enabled: bool
    priority: int
    api_key_masked: str


class ProviderListResponse(BaseModel):
    items: list[ProviderResponse]
    total: int


class ProviderModelsResponse(BaseModel):
    models: list[str]
    total: int


class ProviderCheckResponse(BaseModel):
    ok: bool
    latency_ms: int
    model_count: int


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if not is_admin_email(user.email):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def _fernet() -> Fernet:
    key = get_settings().llm_provider_encryption_key
    if not key:
        raise HTTPException(status_code=500, detail="LLM provider encryption is not configured")
    try:
        return Fernet(key.encode())
    except ValueError as exc:
        raise HTTPException(status_code=500, detail="LLM provider encryption is misconfigured") from exc


def _mask(value: str) -> str:
    return "*" * max(0, len(value) - 4) + value[-4:]


def _response(provider: LlmProvider, fernet: Fernet) -> ProviderResponse:
    key = fernet.decrypt(provider.api_key_encrypted.encode()).decode()
    return ProviderResponse(
        id=provider.id, name=provider.name, base_url=provider.base_url, model=provider.model,
        enabled=provider.enabled, priority=provider.priority, api_key_masked=_mask(key),
    )


@router.get("", response_model=ProviderListResponse)
def list_providers(_: Annotated[User, Depends(require_admin)], db: Annotated[Session, Depends(get_db)]) -> ProviderListResponse:
    fernet = _fernet()
    items = list(db.scalars(select(LlmProvider).order_by(LlmProvider.priority, LlmProvider.name)))
    return ProviderListResponse(items=[_response(item, fernet) for item in items], total=len(items))


@router.get("/{provider_id}", response_model=ProviderResponse)
def get_provider(provider_id: int, _: Annotated[User, Depends(require_admin)], db: Annotated[Session, Depends(get_db)]) -> ProviderResponse:
    provider = db.get(LlmProvider, provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    return _response(provider, _fernet())


def _validate_provider_base_url(value: AnyHttpUrl) -> AnyHttpUrl:
    if value.query or value.fragment or value.username or value.password:
        raise ValueError("Provider base URL cannot contain credentials, query, or fragment")
    return value


async def _request_provider_models(url: str, api_key: str) -> object:
    async with asyncio.timeout(10):
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
            )
            response.raise_for_status()
            return response.json()


async def _fetch_provider_models(provider: LlmProvider) -> list[str]:
    api_key = _fernet().decrypt(provider.api_key_encrypted.encode()).decode()
    try:
        payload = await _request_provider_models(
            f"{provider.base_url.rstrip('/')}/models", api_key
        )
    except (httpx.HTTPError, ValueError, TimeoutError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Provider connection failed",
        ) from exc

    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Provider returned an invalid models response",
        )
    return sorted(
        {
            model_id.strip()
            for item in data
            if isinstance(item, dict)
            and isinstance((model_id := item.get("id")), str)
            and model_id.strip()
        }
    )


@router.get("/{provider_id}/models", response_model=ProviderModelsResponse)
async def fetch_provider_models(
    provider_id: int,
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> ProviderModelsResponse:
    provider = db.get(LlmProvider, provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    models = await _fetch_provider_models(provider)
    return ProviderModelsResponse(models=models, total=len(models))


@router.post("/{provider_id}/check", response_model=ProviderCheckResponse)
async def check_provider_connection(
    provider_id: int,
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> ProviderCheckResponse:
    provider = db.get(LlmProvider, provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    started_at = perf_counter()
    models = await _fetch_provider_models(provider)
    latency_ms = max(0, round((perf_counter() - started_at) * 1000))
    return ProviderCheckResponse(
        ok=True,
        latency_ms=latency_ms,
        model_count=len(models),
    )


@router.post("", response_model=ProviderResponse, status_code=201)
def create_provider(payload: ProviderCreate, _: Annotated[User, Depends(require_admin)], db: Annotated[Session, Depends(get_db)]) -> ProviderResponse:
    if db.scalar(select(LlmProvider).where(LlmProvider.name == payload.name)):
        raise HTTPException(status_code=409, detail="Provider name already exists")
    provider = LlmProvider(
        name=payload.name, base_url=str(payload.base_url).rstrip("/"),
        api_key_encrypted=_fernet().encrypt(payload.api_key.encode()).decode(), model=payload.model,
        enabled=payload.enabled, priority=payload.priority,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return _response(provider, _fernet())


@router.patch("/{provider_id}", response_model=ProviderResponse)
def update_provider(provider_id: int, payload: ProviderUpdate, _: Annotated[User, Depends(require_admin)], db: Annotated[Session, Depends(get_db)]) -> ProviderResponse:
    provider = db.get(LlmProvider, provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] != provider.name:
        if db.scalar(select(LlmProvider).where(LlmProvider.name == data["name"])):
            raise HTTPException(status_code=409, detail="Provider name already exists")
    if "api_key" in data:
        provider.api_key_encrypted = _fernet().encrypt(data.pop("api_key").encode()).decode()
    if "base_url" in data:
        data["base_url"] = str(data["base_url"]).rstrip("/")
    for key, value in data.items():
        setattr(provider, key, value)
    db.commit()
    db.refresh(provider)
    return _response(provider, _fernet())


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_provider(provider_id: int, _: Annotated[User, Depends(require_admin)], db: Annotated[Session, Depends(get_db)]) -> None:
    provider = db.get(LlmProvider, provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    db.delete(provider)
    db.commit()


def provider_settings(db: Session) -> list[dict[str, object]]:
    fernet = _fernet()
    return [{"name": p.name, "base_url": p.base_url, "api_key": fernet.decrypt(p.api_key_encrypted.encode()).decode(), "model": p.model} for p in db.scalars(select(LlmProvider).where(LlmProvider.enabled).order_by(LlmProvider.priority))]


__all__ = ["router", "provider_settings", "require_admin"]
