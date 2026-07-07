from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.config import get_settings


def test_alembic_upgrade_head_creates_budget_and_idempotency_tables(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "migration-smoke.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db_path}")
    get_settings.cache_clear()

    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "alembic"))

    command.upgrade(config, "head")

    engine = create_engine(f"sqlite+pysqlite:///{db_path}")
    try:
        inspector = inspect(engine)
        assert "category_budgets" in inspector.get_table_names()
        bot_log_columns = {column["name"] for column in inspector.get_columns("bot_logs")}
        assert "external_event_id" in bot_log_columns
        assert "transactions" in inspector.get_table_names()
    finally:
        engine.dispose()
        get_settings.cache_clear()
