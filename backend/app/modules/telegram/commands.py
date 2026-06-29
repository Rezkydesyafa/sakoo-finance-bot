from typing import Any

from app.config import get_settings
from app.modules.telegram.client import TelegramClient


BOT_COMMANDS: list[dict[str, str]] = [
    {"command": "start", "description": "Mulai Sakoo"},
    {"command": "help", "description": "Panduan penggunaan"},
    {"command": "saldo", "description": "Cek saldo"},
    {"command": "pengeluaran", "description": "List pengeluaran"},
    {"command": "pemasukan", "description": "List pemasukan"},
    {"command": "laporan", "description": "Laporan keuangan"},
    {"command": "export", "description": "Export laporan PDF"},
    {"command": "riwayat", "description": "Riwayat transaksi"},
]


def register_bot_commands(client: TelegramClient | None = None) -> dict[str, Any]:
    telegram_client = client or _build_client_from_settings()
    return telegram_client.set_my_commands(BOT_COMMANDS)


def _build_client_from_settings() -> TelegramClient:
    settings = get_settings()
    return TelegramClient(
        bot_token=settings.telegram_bot_token,
        base_url=settings.telegram_base_url,
        timeout_seconds=settings.telegram_timeout_seconds,
    )

