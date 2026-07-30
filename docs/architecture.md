# Sakoo Bot Architecture

Sakoo memakai pola modular monolith: satu aplikasi FastAPI, tetapi domain dipisah per module supaya perubahan bot, parser, channel, dan transaksi tidak saling bercampur.

## Request Routing

- `app/main.py` hanya memasang dua router utama:
  - `app.api.router` untuk endpoint HTTP aplikasi di bawah `settings.api_prefix` (`/api`).
  - `app.api.webhooks` untuk webhook platform chat dan health check eksternal.
- `app/api/v1/router.py` menjadi aggregator endpoint API versi saat ini: auth, jobs, media, OCR, reports, STT, dan transactions.
- Path publik lama tetap dipertahankan, misalnya `/api/auth/register`, `/api/transactions`, `/webhook/waha`, `/webhook/telegram`, dan `/health/waha`.

## Channel Adapters

- Adapter platform chat berada langsung di `app.modules.waha` dan `app.modules.telegram`.
- `app.api.webhooks` memasang router kedua adapter tanpa lapisan re-export.

## Bot Flow

- `app.modules.transactions.service` menangani orchestration transaksi dari teks chat: pending confirmation, edit, cancel, command ringan, dan response formatting.
- `app.modules.bot.message_handler` menjadi entry point parsing pesan bot: LLM terkonfigurasi dicoba lebih dahulu, lalu rule parser menjadi fallback.
- `app.modules.bot.response_templates` menjaga gaya respon agar tidak tersebar di service bisnis.

## Parser And LLM

- `app.modules.parser` memegang normalisasi bahasa sehari-hari, intent, amount/date parser, transaction parser, dan model kategori.
- Dataset kategori berada di `app/modules/parser/data/category_dataset.csv`.
- Model kategori hasil training berada di `app/modules/parser/models/category_classifier.joblib`.
- `app.modules.llm` menyediakan provider LLM bawaan dan provider OpenAI-compatible bernama melalui token `custom:<nama>`.
- Provider dapat diurutkan bebas; jika semuanya gagal atau hasilnya tidak valid, alur kembali ke parser lokal.

## Transaction Data Access

- `app.modules.transactions.repository` berisi query berulang untuk kebutuhan bot: category lookup, saldo, total periodik, transaksi terbaru, top expense, dan total kategori.
- `app.modules.transactions.query` tetap dipakai untuk listing/filter endpoint dashboard.
- Service sebaiknya tidak menulis SQL agregasi baru langsung kecuali ada alasan kuat. Tambahkan helper di repository/query layer agar behavior mudah dites dan dipakai ulang.

## Background Jobs

- `app.workers.tasks` menjalankan pekerjaan async seperti OCR, STT, dan PDF report.
- Endpoint webhook hanya enqueue pekerjaan berat, lalu memberi respon/progress message ke user.
- OCR mendukung fallback caption agar user tetap bisa mencatat transaksi walaupun teks gambar tidak cukup terbaca.

## Direction

Untuk pengembangan berikutnya, prioritaskan test kontrak route ketika router berubah dan tambah contoh dataset NLP sebelum menambah hard-coded keyword baru.

