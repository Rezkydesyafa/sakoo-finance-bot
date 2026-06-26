from celery import Celery

from app.config import get_settings


settings = get_settings()

celery_app = Celery(
    "sakoo_finance_bot",
    broker=settings.resolved_celery_broker_url,
    backend=settings.resolved_celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_track_started=True,
    timezone="Asia/Jakarta",
)
