from app.database import SessionLocal
from app.modules.notifications.service import check_budget_notification, dispatch_due_notifications
from app.workers.celery_app import celery_app


@celery_app.task(name="app.notifications.dispatch_due")
def dispatch_due_notifications_job() -> dict[str, int]:
    with SessionLocal() as db:
        return dispatch_due_notifications(db)


@celery_app.task(name="app.notifications.check_budget")
def budget_notification_job(transaction_id: int) -> dict[str, int]:
    with SessionLocal() as db:
        return check_budget_notification(db, transaction_id=transaction_id)
