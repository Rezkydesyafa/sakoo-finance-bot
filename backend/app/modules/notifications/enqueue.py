import logging
from typing import Any

from redis import Redis, RedisError

from app.config import get_settings
from app.workers.celery_app import celery_app


logger = logging.getLogger(__name__)


def enqueue_budget_notification_check(transaction_id: int) -> Any | None:
    if not _broker_available():
        return None
    try:
        return celery_app.send_task(
            "app.notifications.check_budget",
            args=[transaction_id],
            retry=False,
        )
    except Exception:
        logger.exception("Unable to enqueue budget notification for transaction %s", transaction_id)
        return None


def _broker_available() -> bool:
    try:
        return bool(
            Redis.from_url(
                get_settings().resolved_celery_broker_url,
                socket_connect_timeout=0.1,
                socket_timeout=0.1,
            ).ping()
        )
    except (RedisError, OSError, ValueError):
        return False
