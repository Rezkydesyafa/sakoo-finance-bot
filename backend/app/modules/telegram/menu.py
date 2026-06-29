from typing import Any


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

InlineKeyboard = dict[str, list[list[dict[str, str]]]]


def build_main_menu() -> InlineKeyboard:
    return _keyboard(
        [
            [("💰 Saldo", MENU_BALANCE), ("➕ Catat", MENU_ADD)],
            [("📊 Laporan", MENU_REPORT), ("📤 Export PDF", MENU_EXPORT)],
            [("📋 Riwayat", MENU_HISTORY), ("⚙️ Pengaturan", MENU_SETTINGS)],
            [("❓ Bantuan", MENU_HELP)],
        ]
    )


def build_add_menu() -> InlineKeyboard:
    return _keyboard(
        [
            [("💸 Pengeluaran", ADD_EXPENSE), ("💰 Pemasukan", ADD_INCOME)],
            [("🧾 Upload Struk", ADD_RECEIPT), ("🎙 Voice Note", ADD_VOICE)],
            [("⬅️ Kembali", BACK_HOME)],
        ]
    )


def build_report_menu() -> InlineKeyboard:
    return _keyboard(
        [
            [("📅 Hari Ini", REPORT_TODAY), ("📆 Minggu Ini", REPORT_WEEK)],
            [("🗓 Bulan Ini", REPORT_MONTH), ("📊 Per Kategori", REPORT_CATEGORY)],
            [("⬅️ Kembali", BACK_HOME)],
        ]
    )


def build_export_menu() -> InlineKeyboard:
    return _keyboard(
        [
            [("📄 Export Minggu Ini", EXPORT_WEEK)],
            [("📄 Export Bulan Ini", EXPORT_MONTH)],
            [("⬅️ Kembali", BACK_HOME)],
        ]
    )


def build_history_menu() -> InlineKeyboard:
    return _keyboard(
        [
            [("📋 Semua Transaksi", HISTORY_ALL)],
            [("💸 Pengeluaran", HISTORY_EXPENSE), ("💰 Pemasukan", HISTORY_INCOME)],
            [("🔍 Cari Transaksi", HISTORY_SEARCH)],
            [("⬅️ Kembali", BACK_HOME)],
        ]
    )


def build_settings_menu() -> InlineKeyboard:
    return _keyboard(
        [
            [("🔗 Hubungkan Dashboard", SET_LINK)],
            [("🏷 Atur Kategori", SET_CATEGORY), ("💸 Atur Budget", SET_BUDGET)],
            [("⬅️ Kembali", BACK_HOME)],
        ]
    )


def _keyboard(rows: list[list[tuple[str, str]]]) -> InlineKeyboard:
    return {
        "inline_keyboard": [
            [{"text": text, "callback_data": callback_data} for text, callback_data in row]
            for row in rows
        ]
    }


def callback_data_values() -> set[str]:
    values: set[str] = set()
    for keyboard in [
        build_main_menu(),
        build_add_menu(),
        build_report_menu(),
        build_export_menu(),
        build_history_menu(),
        build_settings_menu(),
    ]:
        values.update(
            button["callback_data"]
            for row in keyboard["inline_keyboard"]
            for button in row
        )
    return values


def as_reply_markup(markup: InlineKeyboard | None) -> dict[str, Any] | None:
    return markup

