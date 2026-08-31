from __future__ import annotations

import base64
from datetime import datetime
from decimal import Decimal
from html import escape

from app.modules.reports.schemas import (
    ReportCategoryResponse,
    ReportSummaryResponse,
    ReportTransactionItem,
)

# Load the Sakoo official logo as base64 to embed it dynamically in the HTML template
try:
    with open("/app/public/brand/sakoo-mark.png", "rb") as f:
        LOGO_B64 = base64.b64encode(f.read()).decode("utf-8")
except Exception:
    # Fallback to absolute local path outside docker if run via virtualenv or local dev
    try:
        with open("/home/kinar/dev/sakoo-deploy-pull-fix/frontend/public/brand/sakoo-mark.png", "rb") as f:
            LOGO_B64 = base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        LOGO_B64 = ""

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
    expense_rows = _render_category_rows(expense_categories, is_expense=True)
    income_rows = _render_category_rows(income_categories, is_expense=False)

    logo_src = f"data:image/png;base64,{LOGO_B64}" if LOGO_B64 else ""

    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Sakoo AI - Laporan Keuangan - {escape(period_label)}</title>
  <style>
    @page {{
      size: A4 portrait;
      margin: 16mm 15mm 20mm;
      @bottom-right {{
        content: "Halaman " counter(page) " dari " counter(pages);
        color: #6f6f6f;
        font-size: 8.5px;
      }}
    }}
    * {{ box-sizing: border-box; }}
    body {{
      background: #ffffff;
      color: #202020;
      font-family: Inter, "Helvetica Neue", Helvetica, Arial, sans-serif;
      font-size: 10.5px;
      line-height: 1.45;
      margin: 0;
    }}
    .topline {{
      background: #c7ff00;
      height: 4px;
      margin-bottom: 12px;
      width: 100%;
    }}
    .header {{
      border-bottom: 1px solid #e2e8f0;
      margin-bottom: 14px;
      padding-bottom: 14px;
    }}
    .header-grid {{
      border-collapse: collapse;
      width: 100%;
    }}
    .header-grid td {{
      padding: 0;
      vertical-align: top;
    }}
    .brand-label {{
      color: #6f6f6f;
      font-size: 8.5px;
      font-weight: 700;
      letter-spacing: .13em;
      margin-bottom: 8px;
      text-transform: uppercase;
    }}
    .brand-row {{
      margin-bottom: 8px;
      white-space: nowrap;
    }}
    .brand-logo-img {{
      display: inline-block;
      height: 32px;
      width: 32px;
      vertical-align: middle;
      margin-right: 10px;
    }}
    .brand-name {{
      display: inline-block;
      font-size: 14px;
      font-weight: 800;
      letter-spacing: -0.01em;
      vertical-align: middle;
      color: #202020;
    }}
    .brand-subtitle {{
      color: #6f6f6f;
      display: block;
      font-size: 8.5px;
      font-weight: 500;
      margin-top: 1px;
    }}
    h1 {{
      color: #202020;
      font-size: 26px;
      font-weight: 800;
      letter-spacing: -0.02em;
      line-height: 1.08;
      margin: 12px 0 14px;
    }}
    .meta {{
      border-collapse: collapse;
      color: #444444;
      font-size: 9.5px;
    }}
    .meta td {{
      padding: 2px 12px 2px 0;
    }}
    .meta-label {{
      color: #6f6f6f;
      font-weight: 700;
      width: 60px;
    }}
    .header-note {{
      color: #555555;
      font-size: 9px;
      line-height: 1.5;
      text-align: right;
      white-space: nowrap;
    }}
    .section {{
      margin-top: 16px;
    }}
    .section-title {{
      color: #202020;
      font-size: 13px;
      font-weight: 800;
      letter-spacing: -0.01em;
      margin: 0 0 10px;
      border-bottom: 1.5px solid #202020;
      padding-bottom: 4px;
    }}
    .metrics {{
      border-collapse: separate;
      border-spacing: 8px 0;
      margin-left: -8px;
      width: calc(100% + 16px);
      margin-bottom: 10px;
    }}
    .metric {{
      background: #f7f7f0;
      border: 1px solid #e2e8f0;
      border-left: 4px solid #202020;
      border-radius: 8px;
      padding: 10px 12px;
      width: 25%;
    }}
    .metric.income {{
      border-left-color: #2e7d32;
      background: #f1f8e9;
    }}
    .metric.expense {{
      border-left-color: #d32f2f;
      background: #ffebee;
    }}
    .metric.balance {{
      border-left-color: #c7ff00;
      background: #f9fbe7;
    }}
    .metric-label {{
      color: #6f6f6f;
      font-size: 8px;
      font-weight: 800;
      letter-spacing: .08em;
      text-transform: uppercase;
    }}
    .metric-value {{
      color: #202020;
      font-size: 16px;
      font-weight: 800;
      letter-spacing: -0.01em;
      margin-top: 4px;
      white-space: nowrap;
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
    .panel {{
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 9px;
      min-height: 112px;
      padding: 12px;
    }}
    .panel-title {{
      color: #202020;
      font-size: 11.5px;
      font-weight: 800;
      margin-bottom: 12px;
      border-bottom: 1px solid #e2e8f0;
      padding-bottom: 4px;
    }}
    .category-row {{
      margin-bottom: 12px;
    }}
    .category-row:last-child {{
      margin-bottom: 0;
    }}
    .category-head {{
      display: table;
      width: 100%;
    }}
    .category-name {{
      display: table-cell;
      font-size: 10px;
      font-weight: 800;
      padding-right: 8px;
      color: #202020;
    }}
    .category-total {{
      display: table-cell;
      font-size: 10px;
      font-weight: 800;
      text-align: right;
      white-space: nowrap;
      color: #202020;
    }}
    .category-meta {{
      color: #6f6f6f;
      font-size: 8.5px;
      margin-top: 1px;
    }}
    .bar {{
      background: #e2e8f0;
      border-radius: 999px;
      height: 6px;
      margin-top: 6px;
      overflow: hidden;
      width: 100%;
    }}
    .bar-fill {{
      height: 6px;
    }}
    .bar-fill.expense {{
      background: #d32f2f;
    }}
    .bar-fill.income {{
      background: #2e7d32;
    }}
    table.data {{
      border-collapse: collapse;
      width: 100%;
      margin-top: 4px;
    }}
    table.data thead {{
      display: table-header-group;
    }}
    table.data tr {{
      page-break-inside: avoid;
    }}
    table.data th {{
      border-bottom: 2px solid #202020;
      color: #202020;
      font-size: 8.5px;
      font-weight: 800;
      letter-spacing: .05em;
      padding: 10px 8px;
      text-align: left;
      text-transform: uppercase;
    }}
    table.data td {{
      border-bottom: 1px solid #f1f2f0;
      color: #202020;
      padding: 10px 8px;
      vertical-align: middle;
      font-size: 10px;
    }}
    table.data tbody tr:nth-child(even) td {{
      background: #fafafa;
    }}
    .date-cell {{
      color: #6f6f6f;
      white-space: nowrap;
      width: 80px;
    }}
    .note-cell {{
      min-width: 150px;
    }}
    .note-main {{
      color: #202020;
      font-weight: 600;
    }}
    .note-source {{
      color: #6f6f6f;
      display: block;
      font-size: 8px;
      margin-top: 1px;
    }}
    .category-cell {{
      color: #202020;
      font-weight: 600;
      width: 90px;
    }}
    .type-cell {{
      width: 80px;
    }}
    .amount {{
      font-weight: 700;
      text-align: right;
      white-space: nowrap;
      width: 100px;
    }}
    .amount.income {{
      color: #2e7d32;
    }}
    .amount.expense {{
      color: #d32f2f;
    }}
    .pill {{
      border-radius: 6px;
      display: inline-block;
      font-size: 7.8px;
      font-weight: 800;
      line-height: 1;
      min-width: 58px;
      padding: 4px 6px;
      text-align: center;
      white-space: nowrap;
    }}
    .pill.income {{
      background: #e8f5e9;
      border: 1px solid #c8e6c9;
      color: #2e7d32;
    }}
    .pill.expense {{
      background: #ffeedd;
      border: 1px solid #ffe0b2;
      color: #e65100;
    }}
    .empty {{
      background: #f7f7f0;
      border: 1px dashed #c8c8c8;
      border-radius: 8px;
      color: #6f6f6f;
      padding: 16px;
      text-align: center;
    }}
    .footer-note {{
      border-top: 1px solid #e2e8f0;
      color: #6f6f6f;
      font-size: 8.3px;
      margin-top: 24px;
      padding-top: 9px;
    }}
    .footer-brand {{
      color: #202020;
      font-weight: 800;
      margin-right: 10px;
    }}
  </style>
</head>
<body>
  <div class="topline"></div>
  <div class="header">
    <table class="header-grid">
      <tr>
        <td>
          <div class="brand-label">SAKOO AI FINANCE REPORT</div>
          <div class="brand-row">
            {f'<img class="brand-logo-img" src="{logo_src}" alt="Logo" />' if logo_src else '<span class="brand-mark" style="background:#202020; color:#c7ff00; border-radius:6px; display:inline-block; font-size:11px; font-weight:800; height:28px; line-height:28px; width:28px; text-align:center;">SA</span>'}
            <span class="brand-name">Sakoo. AI<span class="brand-subtitle">Personal Finance, Made Simple</span></span>
          </div>
          <h1>Laporan Keuangan</h1>
          <table class="meta">
            <tr>
              <td class="meta-label">Pemilik</td>
              <td><strong>{escape(user_name)}</strong></td>
            </tr>
            <tr>
              <td class="meta-label">Periode</td>
              <td><strong>{escape(period_label)}</strong></td>
            </tr>
            <tr>
              <td class="meta-label">Dibuat</td>
              <td>{escape(_format_datetime(generated_at))}</td>
            </tr>
          </table>
        </td>
        <td class="header-note">
          Laporan otomatis<br>
          Periode {escape(_short_period_label(summary))}
        </td>
      </tr>
    </table>
  </div>

  <table class="metrics">
    <tr>
      <td class="metric income">
        <div class="metric-label">Pemasukan</div>
        <div class="metric-value">{escape(_format_rupiah(summary.total_income))}</div>
      </td>
      <td class="metric expense">
        <div class="metric-label">Pengeluaran</div>
        <div class="metric-value">{escape(_format_rupiah(summary.total_expense))}</div>
      </td>
      <td class="metric balance">
        <div class="metric-label">Saldo Bersih</div>
        <div class="metric-value">{escape(_format_rupiah(summary.net_balance))}</div>
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
        <td><div class="panel"><div class="panel-title">Pengeluaran</div>{expense_rows}</div></td>
        <td><div class="panel"><div class="panel-title">Pemasukan</div>{income_rows}</div></td>
      </tr>
    </table>
  </div>

  <div class="section">
    <div class="section-title">Daftar Transaksi</div>
    {transaction_rows}
  </div>

  <div class="footer-note">
    <span class="footer-brand">Sakoo. AI</span>
    Laporan ini dibuat otomatis oleh Sakoo AI berdasarkan data transaksi yang tersimpan secara aman.
  </div>
</body>
</html>"""


def _render_transaction_rows(transactions: list[ReportTransactionItem]) -> str:
    if not transactions:
        return '<div class="empty">Belum ada transaksi pada periode ini.</div>'

    rows = []
    for item in transactions:
        amount_class = "income" if item.type == "income" else "expense"
        rows.append(
            "<tr>"
            f'<td class="date-cell">{escape(_format_date(item.transaction_date))}</td>'
            '<td class="note-cell">'
            f'<span class="note-main">{escape(item.description or "-")}</span>'
            f'<span class="note-source">{escape(item.source)}</span>'
            "</td>"
            f'<td class="category-cell">{escape(item.category_name or "Tanpa kategori")}</td>'
            f'<td class="type-cell"><span class="pill {escape(item.type)}">'
            f"{escape(_type_label(item.type))}</span></td>"
            f'<td class="amount {amount_class}">{escape(_format_rupiah(item.amount))}</td>'
            "</tr>"
        )

    return (
        '<table class="data">'
        "<thead><tr>"
        "<th>Tanggal</th>"
        "<th>Catatan</th>"
        "<th>Kategori</th>"
        "<th>Jenis</th>"
        '<th class="amount">Nominal</th>'
        "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _render_category_rows(category_response: ReportCategoryResponse, is_expense: bool = True) -> str:
    if not category_response.items:
        return '<div class="empty">Tidak ada data.</div>'

    fill_class = "expense" if is_expense else "income"
    rows = []
    for item in category_response.items:
        width = max(0, min(float(item.percentage), 100))
        rows.append(
            '<div class="category-row">'
            '<div class="category-head">'
            f'<div class="category-name">{escape(item.category_name)}</div>'
            f'<div class="category-total">{escape(_format_rupiah(item.total_amount))}</div>'
            "</div>"
            '<div class="category-meta">'
            f"{item.transaction_count} transaksi - {_format_percentage(item.percentage)}"
            "</div>"
            '<div class="bar">'
            f'<div class="bar-fill {fill_class}" style="width: {width:.2f}%"></div>'
            "</div>"
            "</div>"
        )
    return "".join(rows)


def _period_label(summary: ReportSummaryResponse) -> str:
    if summary.period_start == summary.period_end:
        return _format_date(summary.period_start)
    return f"{_format_date(summary.period_start)} - {_format_date(summary.period_end)}"


def _short_period_label(summary: ReportSummaryResponse) -> str:
    if summary.period_start.year == summary.period_end.year and (
        summary.period_start.month == summary.period_end.month
    ):
        return f"{MONTH_LABELS[summary.period_start.month]} {summary.period_start.year}"
    return _period_label(summary)


def _format_date(value) -> str:
    return f"{value.day:02d} {MONTH_LABELS[value.month]} {value.year}"


def _format_datetime(value: datetime) -> str:
    return f"{_format_date(value.date())} {value:%H:%M}"


def _format_rupiah(value: Decimal) -> str:
    sign = "-" if value < 0 else ""
    number = f"{abs(int(value)):,}".replace(",", ".")
    return f"{sign}Rp{number}"


def _format_percentage(value: Decimal) -> str:
    normalized = value.quantize(Decimal("0.01"))
    if normalized == normalized.to_integral_value():
        return f"{int(normalized)}%"
    return f"{normalized}%"


def _type_label(value: str) -> str:
    return "Pemasukan" if value == "income" else "Pengeluaran"
