import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AccountLinkingCode, UserPlatformAccount
from app.modules.waha.parser import ParsedWahaMessage


LINKING_COMMAND_RE = re.compile(r"^\s*hubungkan\s+([A-Za-z0-9_-]{4,32})\s*$", re.IGNORECASE)

@dataclass(frozen=True)
class LinkingResult:
    action: str
    status: str
    reply_text: str | None = None
    user_id: int | None = None
    error_message: str | None = None

    def to_log_payload(self) -> dict[str, str | int | None]:
        return asdict(self)


def extract_linking_code(text: str | None) -> str | None:
    if not text:
        return None
    match = LINKING_COMMAND_RE.match(text)
    return match.group(1).upper() if match else None


def handle_account_linking(
    *,
    db: Session,
    parsed: ParsedWahaMessage,
    current_user_id: int | None,
) -> LinkingResult:
    if parsed.from_me:
        return LinkingResult(action="from_me", status="from_me", user_id=current_user_id)

    code_value = extract_linking_code(parsed.text)
    if code_value:
        return _link_whatsapp_account(db=db, parsed=parsed, code_value=code_value)

    if current_user_id is None:
        return LinkingResult(
            action="instruction",
            status="unlinked",
            reply_text=_linking_instruction_message(),
        )

    return LinkingResult(action="ignored", status="linked", user_id=current_user_id)


def _link_whatsapp_account(
    *,
    db: Session,
    parsed: ParsedWahaMessage,
    code_value: str,
) -> LinkingResult:
    if not parsed.chat_id or not parsed.platform_user_id:
        return LinkingResult(
            action="link",
            status="failed",
            reply_text="Gagal membaca nomor WhatsApp. Silakan kirim ulang pesan linking.",
            error_message="missing_whatsapp_identity",
        )

    linking_code = db.scalar(
        select(AccountLinkingCode).where(
            func.lower(AccountLinkingCode.code) == code_value.lower(),
        )
    )
    if linking_code is None:
        return LinkingResult(
            action="link",
            status="invalid",
            reply_text="Kode linking tidak valid. Cek kembali kode dari dashboard.",
            error_message="invalid_code",
        )

    if linking_code.used_at is not None:
        return LinkingResult(
            action="link",
            status="invalid",
            reply_text="Kode linking sudah pernah digunakan. Buat kode baru dari dashboard.",
            error_message="used_code",
        )

    if _is_expired(linking_code.expired_at):
        return LinkingResult(
            action="link",
            status="expired",
            reply_text="Kode linking sudah expired. Buat kode baru dari dashboard.",
            error_message="expired_code",
        )

    existing_by_number = db.scalar(
        select(UserPlatformAccount).where(
            UserPlatformAccount.platform == "whatsapp",
            UserPlatformAccount.platform_user_id == parsed.platform_user_id,
        )
    )
    if existing_by_number and existing_by_number.user_id != linking_code.user_id:
        return LinkingResult(
            action="link",
            status="conflict",
            reply_text="Nomor WhatsApp ini sudah terhubung ke akun lain.",
            error_message="platform_user_conflict",
        )

    account = db.scalar(
        select(UserPlatformAccount).where(
            UserPlatformAccount.user_id == linking_code.user_id,
            UserPlatformAccount.platform == "whatsapp",
        )
    )
    if account is None:
        account = UserPlatformAccount(
            user_id=linking_code.user_id,
            platform="whatsapp",
        )
        db.add(account)

    now = datetime.now(timezone.utc)
    account.platform_user_id = parsed.platform_user_id
    account.phone_number = parsed.platform_user_id
    account.chat_id = parsed.chat_id
    account.linked_at = now
    account.is_active = True
    linking_code.used_at = now

    return LinkingResult(
        action="link",
        status="success",
        reply_text="Nomor WhatsApp berhasil terhubung ke akun dashboard.",
        user_id=linking_code.user_id,
    )


def _is_expired(expired_at: datetime) -> bool:
    comparable_expired_at = expired_at
    if comparable_expired_at.tzinfo is None:
        comparable_expired_at = comparable_expired_at.replace(tzinfo=timezone.utc)
    return comparable_expired_at <= datetime.now(timezone.utc)


def _linking_instruction_message() -> str:
    app_url = get_settings().app_base_url.rstrip("/")
    return (
        "Silakan daftar atau login di dashboard Sakoo untuk memulai bot:\n"
        f"{app_url}/register\n\n"
        "Setelah masuk, buka Connected Bots, buat kode linking, lalu kirim ke WhatsApp ini:\n"
        "hubungkan KODE"
    )
