from typing import Any

from app.config import get_settings


MENU_BALANCE = "MENU_BALANCE"
MENU_ADD = "MENU_ADD"
MENU_REPORT = "MENU_REPORT"
MENU_EXPORT = "MENU_EXPORT"
MENU_HISTORY = "MENU_HISTORY"
MENU_SETTINGS = "MENU_SETTINGS"
MENU_HELP = "MENU_HELP"

ADD_EXPENSE = "ADD_EXPENSE"
ADD_INCOME = "ADD_INCOME"
ADD_RECEIPT = "ADD_RECEIPT"
ADD_VOICE = "ADD_VOICE"

REPORT_TODAY = "REPORT_TODAY"
REPORT_WEEK = "REPORT_WEEK"
REPORT_MONTH = "REPORT_MONTH"
REPORT_CATEGORY = "REPORT_CATEGORY"

EXPORT_WEEK = "EXPORT_WEEK"
EXPORT_MONTH = "EXPORT_MONTH"

HISTORY_ALL = "HISTORY_ALL"
HISTORY_EXPENSE = "HISTORY_EXPENSE"
HISTORY_INCOME = "HISTORY_INCOME"
HISTORY_SEARCH = "HISTORY_SEARCH"

SET_LINK = "SET_LINK"
SET_CATEGORY = "SET_CATEGORY"
SET_BUDGET = "SET_BUDGET"

BACK_HOME = "BACK_HOME"

CALLBACK_DATA_VALUES = {
    MENU_BALANCE,
    MENU_ADD,
    MENU_REPORT,
    MENU_EXPORT,
    MENU_HISTORY,
    MENU_SETTINGS,
    MENU_HELP,
    ADD_EXPENSE,
    ADD_INCOME,
    ADD_RECEIPT,
    ADD_VOICE,
    REPORT_TODAY,
    REPORT_WEEK,
    REPORT_MONTH,
    REPORT_CATEGORY,
    EXPORT_WEEK,
    EXPORT_MONTH,
    HISTORY_ALL,
    HISTORY_EXPENSE,
    HISTORY_INCOME,
    HISTORY_SEARCH,
    SET_LINK,
    SET_CATEGORY,
    SET_BUDGET,
    BACK_HOME,
}


def dashboard_url() -> str:
    return get_settings().telegram_dashboard_url.rstrip("/")


def dashboard_web_app_button(text: str = "Buka Dashboard") -> dict[str, Any]:
    return {"text": text, "web_app": {"url": dashboard_url()}}


def build_main_menu() -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [dashboard_web_app_button("Sakoo Dashboard")],
            [_callback_button("Saldo", MENU_BALANCE), _callback_button("Catat", MENU_ADD)],
            [_callback_button("Laporan", MENU_REPORT), _callback_button("Export PDF", MENU_EXPORT)],
            [_callback_button("Riwayat", MENU_HISTORY), _callback_button("Pengaturan", MENU_SETTINGS)],
            [_callback_button("Bantuan", MENU_HELP)],
        ]
    }


def build_add_menu() -> dict[str, Any]:
    return _keyboard(
        [
            [("Pengeluaran", ADD_EXPENSE), ("Pemasukan", ADD_INCOME)],
            [("Upload Struk", ADD_RECEIPT), ("Voice Note", ADD_VOICE)],
            [("Kembali", BACK_HOME)],
        ]
    )


def build_report_menu() -> dict[str, Any]:
    return _keyboard(
        [
            [("Hari Ini", REPORT_TODAY), ("Minggu Ini", REPORT_WEEK)],
            [("Bulan Ini", REPORT_MONTH), ("Per Kategori", REPORT_CATEGORY)],
            [("Kembali", BACK_HOME)],
        ]
    )


def build_export_menu() -> dict[str, Any]:
    return _keyboard(
        [
            [("Export Minggu Ini", EXPORT_WEEK)],
            [("Export Bulan Ini", EXPORT_MONTH)],
            [("Kembali", BACK_HOME)],
        ]
    )


def build_history_menu() -> dict[str, Any]:
    return _keyboard(
        [
            [("Semua Transaksi", HISTORY_ALL)],
            [("Pengeluaran", HISTORY_EXPENSE), ("Pemasukan", HISTORY_INCOME)],
            [("Cari Transaksi", HISTORY_SEARCH)],
            [("Kembali", BACK_HOME)],
        ]
    )


def build_settings_menu() -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [dashboard_web_app_button("Buka Dashboard")],
            [_callback_button("Hubungkan Dashboard", SET_LINK)],
            [_callback_button("Atur Kategori", SET_CATEGORY), _callback_button("Atur Budget", SET_BUDGET)],
            [_callback_button("Kembali", BACK_HOME)],
        ]
    }


def build_link_menu() -> dict[str, Any]:
    app_url = dashboard_url()
    return {
        "inline_keyboard": [
            [{"text": "Buka Dashboard", "web_app": {"url": app_url}}],
            [{"text": "Daftar/Login Dashboard", "url": f"{app_url}/register"}],
            [{"text": "Kembali", "callback_data": BACK_HOME}],
        ]
    }


def _keyboard(rows: list[list[tuple[str, str]]]) -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [_callback_button(text, callback_data) for text, callback_data in row]
            for row in rows
        ]
    }


def _callback_button(text: str, callback_data: str) -> dict[str, Any]:
    return {"text": text, "callback_data": callback_data}


def callback_data_values() -> set[str]:
    return CALLBACK_DATA_VALUES


def as_reply_markup(markup: dict[str, Any] | None) -> dict[str, Any] | None:
    return markup
