from app.config import Settings, get_settings


def is_admin_email(email: str, settings: Settings | None = None) -> bool:
    active_settings = settings or get_settings()
    allowed = {
        value.strip().lower()
        for value in active_settings.admin_emails.split(",")
        if value.strip()
    }
    return bool(allowed) and email.strip().lower() in allowed


__all__ = ["is_admin_email"]
