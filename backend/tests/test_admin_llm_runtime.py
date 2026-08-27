from __future__ import annotations

from collections.abc import Iterator

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import LlmProvider
from app.modules.llm.llm_router import get_llm_providers


@pytest.fixture()
def session_factory() -> Iterator[sessionmaker[Session]]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_enabled_database_providers_override_env_chain_in_priority_order(
    session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    key = Fernet.generate_key()
    monkeypatch.setenv("LLM_PROVIDER_ENCRYPTION_KEY", key.decode())
    from app.config import get_settings
    get_settings.cache_clear()
    with session_factory() as db:  # type: Session
        fernet = Fernet(key)
        db.add_all([
            LlmProvider(name="slow", base_url="https://slow.example", api_key_encrypted=fernet.encrypt(b"slow-key").decode(), model="slow-model", priority=20),
            LlmProvider(name="fast", base_url="https://fast.example", api_key_encrypted=fernet.encrypt(b"fast-key").decode(), model="fast-model", priority=1),
        ])
        db.commit()
        settings = get_settings()
        providers = get_llm_providers(settings, db=db)

    assert [provider.provider_name for provider in providers] == ["custom:fast", "custom:slow"]
    assert [provider.config.api_key for provider in providers] == ["fast-key", "slow-key"]
