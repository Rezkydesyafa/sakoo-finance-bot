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
  <title>SAKOO AI - Laporan Keuangan - {escape(period_label)}</title>
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
      color: #111111;
      font-family: Inter, "Helvetica Neue", Helvetica, Arial, sans-serif;
      font-size: 10.5px;
      line-height: 1.45;
      margin: 0;
    }}
    .topline {{
      background: #111111;
      height: 1.5px;
      margin-bottom: 12px;
      width: 100%;
    }}
    .header {{
      border-bottom: 1px solid #d6d6d6;
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
      color: #444444;
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
    .brand-mark {{
      border: 1px solid #111111;
      display: inline-block;
      font-size: 8px;
      font-weight: 800;
      height: 24px;
      letter-spacing: .02em;
      line-height: 24px;
      margin-right: 8px;
      text-align: center;
      vertical-align: middle;
      width: 24px;
    }}
    .brand-name {{
      display: inline-block;
      font-size: 12px;
      font-weight: 800;
      letter-spacing: .01em;
      vertical-align: middle;
    }}
    .brand-subtitle {{
      color: #666666;
      display: block;
      font-size: 8.5px;
      font-weight: 500;
      margin-top: 1px;
    }}
    h1 {{
      color: #000000;
      font-size: 30px;
      font-weight: 800;
      letter-spacing: 0;
      line-height: 1.08;
      margin: 8px 0 10px;
    }}
    .meta {{
      border-collapse: collapse;
      color: #444444;
      font-size: 9.5px;
    }}
    .meta td {{
      padding: 1px 12px 1px 0;
    }}
    .meta-label {{
      color: #666666;
      font-weight: 700;
    }}
    .header-note {{
      color: #555555;
      font-size: 9px;
      line-height: 1.5;
      text-align: right;
      white-space: nowrap;
    }}
    .section {{
      margin-top: 14px;
    }}
    .section-title {{
      color: #000000;
      font-size: 14px;
      font-weight: 800;
      letter-spacing: 0;
      margin: 0 0 8px;
    }}
    .metrics {{
      border-collapse: separate;
      border-spacing: 8px 0;
      margin-left: -8px;
      width: calc(100% + 16px);
    }}
    .metric {{
      background: #ffffff;
      border: 1px solid #b8b8b8;
      border-radius: 8px;
      padding: 12px 10px;
      width: 25%;
    }}
    .metric-label {{
      color: #555555;
      font-size: 8px;
      font-weight: 800;
      letter-spacing: .08em;
      text-transform: uppercase;
    }}
    .metric-value {{
      color: #000000;
      font-size: 18px;
      font-weight: 800;
      letter-spacing: 0;
      margin-top: 5px;
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
      border: 1px solid #d2d2d2;
      border-radius: 9px;
      min-height: 112px;
      padding: 12px;
    }}
    .panel-title {{
      color: #000000;
      font-size: 12px;
      font-weight: 800;
      margin-bottom: 10px;
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
    }}
    .category-total {{
      display: table-cell;
      font-size: 10px;
      font-weight: 800;
      text-align: right;
      white-space: nowrap;
    }}
    .category-meta {{
      color: #666666;
      font-size: 8.5px;
      margin-top: 1px;
    }}
    .bar {{
      background: #e8e8e8;
      border-radius: 999px;
      height: 5px;
      margin-top: 6px;
      overflow: hidden;
      width: 100%;
    }}
    .bar-fill {{
      background: #111111;
      height: 5px;
    }}
    table.data {{
      border-collapse: collapse;
      width: 100%;
    }}
    table.data thead {{
      display: table-header-group;
    }}
    table.data tr {{
      page-break-inside: avoid;
    }}
    table.data th {{
      background: #f1f1f1;
      border-bottom: 1px solid #cfcfcf;
      color: #333333;
      font-size: 7.8px;
      font-weight: 800;
      letter-spacing: .07em;
      padding: 8px 7px;
      text-align: left;
      text-transform: uppercase;
    }}
    table.data td {{
      border-bottom: 1px solid #e3e3e3;
      color: #111111;
      padding: 9px 7px;
      vertical-align: top;
    }}
    table.data tbody tr:nth-child(even) td {{
      background: #fafafa;
    }}
    .date-cell {{
      color: #333333;
      white-space: nowrap;
      width: 76px;
    }}
    .note-cell {{
      min-width: 150px;
    }}
    .note-main {{
      color: #111111;
      font-weight: 700;
    }}
    .note-source {{
      color: #777777;
      display: block;
      font-size: 8px;
      margin-top: 1px;
    }}
    .category-cell {{
      color: #222222;
      font-weight: 700;
      width: 86px;
    }}
    .type-cell {{
      width: 82px;
    }}
    .amount {{
      font-weight: 800;
      text-align: right;
      white-space: nowrap;
      width: 92px;
    }}
    .pill {{
      border-radius: 999px;
      display: inline-block;
      font-size: 7.8px;
      font-weight: 800;
      line-height: 1;
      min-width: 58px;
      padding: 4px 7px;
      text-align: center;
      white-space: nowrap;
    }}
    .pill.income {{
      background: #ffffff;
      border: 1px solid #111111;
      color: #000000;
    }}
    .pill.expense {{
      background: #eeeeee;
      border: 1px solid #bdbdbd;
      color: #000000;
    }}
    .empty {{
      background: #fafafa;
      border: 1px dashed #c8c8c8;
      border-radius: 8px;
      color: #666666;
      padding: 16px;
      text-align: center;
    }}
    .footer-note {{
      border-top: 1px solid #d8d8d8;
      color: #777777;
      font-size: 8.3px;
      margin-top: 18px;
      padding-top: 9px;
    }}
    .footer-brand {{
      color: #000000;
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
            <span class="brand-mark">SA</span>
            <span class="brand-name">SAKOO AI<span class="brand-subtitle">Finance Intelligence</span></span>
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
      <td class="metric">
        <div class="metric-label">Pemasukan</div>
        <div class="metric-value">{escape(_format_rupiah(summary.total_income))}</div>
      </td>
      <td class="metric">
        <div class="metric-label">Pengeluaran</div>
        <div class="metric-value">{escape(_format_rupiah(summary.total_expense))}</div>
      </td>
      <td class="metric">
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
    <span class="footer-brand">SAKOO AI</span>
    Laporan ini dibuat otomatis oleh SAKOO AI berdasarkan data transaksi yang tersimpan.
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
            f'<td class="date-cell">{escape(_format_date(item.transaction_date))}</td>'
            '<td class="note-cell">'
            f'<span class="note-main">{escape(item.description or "-")}</span>'
            f'<span class="note-source">{escape(item.source)}</span>'
            "</td>"
            f'<td class="category-cell">{escape(item.category_name or "Tanpa kategori")}</td>'
            f'<td class="type-cell"><span class="pill {escape(item.type)}">'
            f"{escape(_type_label(item.type))}</span></td>"
            f'<td class="amount">{escape(_format_rupiah(item.amount))}</td>'
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


def _render_category_rows(category_response: ReportCategoryResponse) -> str:
    if not category_response.items:
        return '<div class="empty">Tidak ada data.</div>'

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
            f'<div class="bar-fill" style="width: {width:.2f}%"></div>'
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
