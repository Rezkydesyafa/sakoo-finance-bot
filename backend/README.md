# Sakoo Backend

Backend Sakoo adalah aplikasi FastAPI dengan modul yang dikelompokkan berdasarkan fitur.

## Peta kode

```text
app/
├── main.py                 # Membuat aplikasi dan health endpoint
├── config.py               # Validasi environment variable
├── database.py             # SQLAlchemy engine dan session
├── models/                 # Model identity, finance, dan operations
├── api/
│   ├── v1/router.py        # Registrasi REST API
│   └── webhooks.py         # Registrasi webhook Telegram dan WAHA
└── modules/
    ├── auth/               # Login dan autentikasi
    ├── bot/                # Parsing awal, state, respons, channel flow
    ├── budgets/            # Budget kategori
    ├── llm/                # Provider dan fallback LLM
    ├── notifications/      # Preferensi dan pengiriman notifikasi
    ├── parser/             # Parser transaksi lokal
    ├── telegram/           # Adapter Telegram
    ├── transactions/       # CRUD dan alur percakapan transaksi
    └── waha/               # Adapter WhatsApp/WAHA
```

`transactions/service.py` adalah public facade. Orkestrasi berada di
`transaction_flow.py`, sedangkan implementasi percakapan dipisahkan secara fisik
ke `pending_flow.py`, `budget_commands.py`, dan `finance_chat.py`.

## Alur pesan

```text
Webhook Telegram/WAHA
  → validasi dan account linking
  → channel_flow: voice → receipt → PDF → text transaction
  → transaction_flow
  → LLM provider pertama
  → provider berikutnya jika gagal
  → parser lokal jika seluruh provider gagal
  → konfirmasi atau simpan transaksi
```

Rate limit LLM berlaku untuk seluruh provider. Parser lokal tidak memakai kuota
LLM dan tetap menjadi fallback terakhir.

## Menjalankan backend

```powershell
cd backend
python -m pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Konfigurasi dibaca dari `.env` di root project. Gunakan `.env.example` sebagai
referensi dan jangan commit API key.

## Pengujian

```powershell
cd backend
python -m pytest -q
```

Quality gate lokal:

```powershell
ruff check --no-cache app tests
pyright
```

Test dapat dijalankan per area:

```powershell
python -m pytest -q tests/test_transactions_crud.py
python -m pytest -q tests/test_llm_first_parser.py tests/test_llm_validator.py
python -m pytest -q tests/test_telegram_webhook.py tests/test_waha_health.py
```

Migration diverifikasi oleh `tests/test_migrations.py`. Tambahkan migration
Alembic setiap kali schema database berubah.
