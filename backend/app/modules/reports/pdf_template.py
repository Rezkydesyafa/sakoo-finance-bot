from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from html import escape

from app.modules.reports.schemas import (
    ReportCategoryResponse,
    ReportSummaryResponse,
    ReportTransactionItem,
)


MONTH_LABELS = {
    1: "Jan",
    2: "Feb",
    3: "Mar",
    4: "Apr",
    5: "Mei",
    6: "Jun",
    7: "Jul",
    8: "Agu",
    9: "Sep",
    10: "Okt",
    11: "Nov",
    12: "Des",
}


def render_report_pdf_html(
    *,
    user_name: str,
    summary: ReportSummaryResponse,
    expense_categories: ReportCategoryResponse,
    income_categories: ReportCategoryResponse,
    generated_at: datetime,
) -> str:
    period_label = _period_label(summary)
    transaction_rows = _render_transaction_rows(summary.transactions)
    expense_rows = _render_category_rows(expense_categories)
    income_rows = _render_category_rows(income_categories)

    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Laporan Keuangan - {escape(period_label)}</title>
  <style>
    @page {{
      size: A4;
      margin: 16mm 14mm 18mm;
      @bottom-right {{
        content: "Halaman " counter(page) " / " counter(pages);
        color: #7b8794;
        font-size: 9px;
      }}
    }}
    * {{ box-sizing: border-box; }}
    body {{
      color: #172033;
      font-family: Arial, Helvetica, sans-serif;
      font-size: 11px;
      line-height: 1.45;
      margin: 0;
    }}
    .topline {{
      background: #1f7a5a;
      height: 6px;
      margin-bottom: 18px;
      width: 100%;
    }}
    .header {{
      border-bottom: 1px solid #d8dee8;
      margin-bottom: 18px;
      padding-bottom: 16px;
    }}
    .brand {{
      color: #1f7a5a;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: .08em;
      text-transform: uppercase;
    }}
    h1 {{
      color: #111827;
      font-size: 28px;
      line-height: 1.15;
      margin: 5px 0 8px;
    }}
    .meta {{
      color: #5d6675;
      font-size: 10.5px;
    }}
    .section {{
      margin-top: 18px;
    }}
    .section-title {{
      color: #111827;
      font-size: 14px;
      font-weight: 700;
      margin: 0 0 9px;
    }}
    .metrics {{
      border-collapse: separate;
      border-spacing: 8px 0;
      margin-left: -8px;
      width: calc(100% + 16px);
    }}
    .metric {{
      background: #f6f8fb;
      border: 1px solid #dce3ec;
      border-radius: 6px;
      padding: 12px 11px;
      width: 25%;
    }}
    .metric-label {{
      color: #667085;
      font-size: 9px;
      font-weight: 700;
      letter-spacing: .05em;
      text-transform: uppercase;
    }}
    .metric-value {{
      color: #111827;
      font-size: 17px;
      font-weight: 700;
      margin-top: 4px;
      white-space: nowrap;
    }}
    .metric-value.income {{ color: #147a50; }}
    .metric-value.expense {{ color: #b42318; }}
    .metric-value.balance {{ color: #164e8f; }}
    .panel {{
      border: 1px solid #dce3ec;
      border-radius: 6px;
      padding: 12px;
    }}
    .two-col {{
      border-collapse: separate;
      border-spacing: 10px 0;
      margin-left: -10px;
      width: calc(100% + 20px);
    }}
    .two-col td {{
      vertical-align: top;
      width: 50%;
    }}
    table.data {{
      border-collapse: collapse;
      width: 100%;
    }}
    table.data th {{
      background: #f3f6fa;
      border-bottom: 1px solid #dce3ec;
      color: #475467;
      font-size: 9px;
      letter-spacing: .04em;
      padding: 8px 7px;
      text-align: left;
      text-transform: uppercase;
    }}
    table.data td {{
      border-bottom: 1px solid #edf1f6;
      padding: 8px 7px;
      vertical-align: top;
    }}
    .amount {{
      font-weight: 700;
      text-align: right;
      white-space: nowrap;
    }}
    .muted {{ color: #667085; }}
    .pill {{
      border-radius: 999px;
      display: inline-block;
      font-size: 9px;
      font-weight: 700;
      padding: 2px 7px;
    }}
    .pill.income {{ background: #e6f4ee; color: #147a50; }}
    .pill.expense {{ background: #fdecec; color: #b42318; }}
    .category-row {{
      margin-bottom: 10px;
    }}
    .category-head {{
      display: table;
      width: 100%;
    }}
    .category-name {{
      display: table-cell;
      font-weight: 700;
    }}
    .category-total {{
      display: table-cell;
      font-weight: 700;
      text-align: right;
      white-space: nowrap;
    }}
    .bar {{
      background: #edf1f6;
      border-radius: 999px;
      height: 7px;
      margin-top: 5px;
      overflow: hidden;
    }}
    .bar-fill {{
      background: #1f7a5a;
      height: 7px;
    }}
    .empty {{
      background: #f8fafc;
      border: 1px dashed #cbd5e1;
      border-radius: 6px;
      color: #667085;
      padding: 18px;
      text-align: center;
    }}
    .footer-note {{
      color: #7b8794;
      font-size: 9px;
      margin-top: 16px;
    }}
  </style>
</head>
<body>
  <div class="topline"></div>
  <div class="header">
    <div class="brand">Sakoo Finance Bot</div>
    <h1>Laporan Keuangan</h1>
    <div class="meta">
      Pemilik: <strong>{escape(user_name)}</strong><br>
      Periode: <strong>{escape(period_label)}</strong><br>
      Dibuat: {escape(_format_datetime(generated_at))}
    </div>
  </div>

  <table class="metrics">
    <tr>
      <td class="metric">
        <div class="metric-label">Pemasukan</div>
        <div class="metric-value income">{escape(_format_rupiah(summary.total_income))}</div>
      </td>
      <td class="metric">
        <div class="metric-label">Pengeluaran</div>
        <div class="metric-value expense">{escape(_format_rupiah(summary.total_expense))}</div>
      </td>
      <td class="metric">
        <div class="metric-label">Saldo Bersih</div>
        <div class="metric-value balance">{escape(_format_rupiah(summary.net_balance))}</div>
      </td>
      <td class="metric">
        <div class="metric-label">Transaksi</div>
        <div class="metric-value">{summary.transaction_count}</div>
      </td>
    </tr>
  </table>

  <div class="section">
    <div class="section-title">Ringkasan Kategori</div>
    <table class="two-col">
      <tr>
        <td><div class="panel"><div class="section-title">Pengeluaran</div>{expense_rows}</div></td>
        <td><div class="panel"><div class="section-title">Pemasukan</div>{income_rows}</div></td>
      </tr>
    </table>
  </div>

  <div class="section">
    <div class="section-title">Daftar Transaksi</div>
    {transaction_rows}
  </div>

  <div class="footer-note">
    Laporan ini dibuat otomatis dari data transaksi yang tersimpan di Sakoo Finance Bot.
  </div>
</body>
</html>"""


def _render_transaction_rows(transactions: list[ReportTransactionItem]) -> str:
    if not transactions:
        return '<div class="empty">Belum ada transaksi pada periode ini.</div>'

    rows = []
    for item in transactions:
        rows.append(
            "<tr>"
            f"<td>{escape(_format_date(item.transaction_date))}</td>"
            f"<td>{escape(item.description or '-')}<br>"
            f"<span class=\"muted\">{escape(item.source)}</span></td>"
            f"<td>{escape(item.category_name or 'Tanpa kategori')}</td>"
            f"<td><span class=\"pill {escape(item.type)}\">{escape(_type_label(item.type))}</span></td>"
            f"<td class=\"amount\">{escape(_format_rupiah(item.amount))}</td>"
            "</tr>"
        )

    return (
        '<table class="data">'
        "<thead><tr><th>Tanggal</th><th>Catatan</th><th>Kategori</th>"
        "<th>Jenis</th><th class=\"amount\">Nominal</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _render_category_rows(category_response: ReportCategoryResponse) -> str:
    if not category_response.items:
        return '<div class="empty">Tidak ada data.</div>'

    rows = []
    for item in category_response.items[:6]:
        width = max(0, min(float(item.percentage), 100))
        rows.append(
            '<div class="category-row">'
            '<div class="category-head">'
            f'<div class="category-name">{escape(item.category_name)}</div>'
            f'<div class="category-total">{escape(_format_rupiah(item.total_amount))}</div>'
            "</div>"
            f'<div class="muted">{item.transaction_count} transaksi - {item.percentage}%</div>'
            '<div class="bar">'
            f'<div class="bar-fill" style="width: {width:.2f}%"></div>'
            "</div>"
            "</div>"
        )
    return "".join(rows)


def _period_label(summary: ReportSummaryResponse) -> str:
    if summary.period_start == summary.period_end:
        return _format_date(summary.period_start)
    return f"{_format_date(summary.period_start)} - {_format_date(summary.period_end)}"


def _format_date(value) -> str:
    return f"{value.day:02d} {MONTH_LABELS[value.month]} {value.year}"


def _format_datetime(value: datetime) -> str:
    return f"{_format_date(value.date())} {value:%H:%M}"


def _format_rupiah(value: Decimal) -> str:
    sign = "-" if value < 0 else ""
    number = f"{abs(int(value)):,}".replace(",", ".")
    return f"{sign}Rp{number}"


def _type_label(value: str) -> str:
    return "Pemasukan" if value == "income" else "Pengeluaran"
