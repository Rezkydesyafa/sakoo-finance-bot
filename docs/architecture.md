# Sakoo Bot Architecture

Sakoo memakai pola modular monolith: satu aplikasi FastAPI, tetapi domain dipisah per module supaya perubahan bot, parser, channel, dan transaksi tidak saling bercampur.

## Request Routing

- `app/main.py` hanya memasang dua router utama:
  - `app.api.router` untuk endpoint HTTP aplikasi di bawah `settings.api_prefix` (`/api`).
  - `app.api.webhooks` untuk webhook platform chat dan health check eksternal.
- `app/api/v1/router.py` menjadi aggregator endpoint API versi saat ini: auth, jobs, media, OCR, reports, STT, dan transactions.
- Path publik lama tetap dipertahankan, misalnya `/api/auth/register`, `/api/transactions`, `/webhook/waha`, `/webhook/telegram`, dan `/health/waha`.

## Channel Adapters

- Namespace baru `app.modules.channels` menjadi pintu masuk adapter platform chat.
- Saat ini namespace tersebut masih me-reexport module lama:
  - `app.modules.channels.waha` -> `app.modules.waha`
  - `app.modules.channels.telegram` -> `app.modules.telegram`
- Pendekatan ini menjaga kompatibilitas import lama sambil memberi tempat yang lebih jelas untuk integrasi platform baru seperti WhatsApp Cloud API, Discord, atau LINE.

## Bot Flow

- `app.modules.transactions.service` menangani orchestration transaksi dari teks chat: pending confirmation, edit, cancel, command ringan, dan response formatting.
- `app.modules.bot.service` menjadi entry point aplikasi untuk parsing pesan bot.
- `app.modules.bot.message_handler` tetap fokus ke pipeline NLP: rule parser, category model, dan LLM fallback hemat token.
- `app.modules.bot.response_templates` menjaga gaya respon agar tidak tersebar di service bisnis.

## Parser And LLM

- `app.modules.parser` memegang normalisasi bahasa sehari-hari, intent, amount/date parser, transaction parser, dan model kategori.
- Dataset kategori berada di `app/modules/parser/data/category_dataset.csv`.
- Model kategori hasil training berada di `app/modules/parser/models/category_classifier.joblib`.
- `app.modules.llm` hanya dipakai sebagai fallback saat parser lokal kurang yakin, sehingga token tetap hemat.

## Transaction Data Access

- `app.modules.transactions.repository` berisi query berulang untuk kebutuhan bot: category lookup, saldo, total periodik, transaksi terbaru, top expense, dan total kategori.
- `app.modules.transactions.query` tetap dipakai untuk listing/filter endpoint dashboard.
- Service sebaiknya tidak menulis SQL agregasi baru langsung kecuali ada alasan kuat. Tambahkan helper di repository/query layer agar behavior mudah dites dan dipakai ulang.

## Background Jobs

- `app.workers.tasks` menjalankan pekerjaan async seperti OCR, STT, dan PDF report.
- Endpoint webhook hanya enqueue pekerjaan berat, lalu memberi respon/progress message ke user.
- OCR mendukung fallback caption agar user tetap bisa mencatat transaksi walaupun teks gambar tidak cukup terbaca.

## Direction

Untuk pengembangan berikutnya, prioritaskan:

- Memindahkan isi module lama `waha` dan `telegram` secara bertahap ke `channels` setelah import lama tidak lagi dipakai.
- Memecah `transactions.service` menjadi submodule kecil jika flow semakin besar, misalnya `pending_flow.py`, `command_responses.py`, dan `save_transaction.py`.
- Menambah test kontrak route setiap kali router baru ditambahkan.
- Menambah contoh dataset NLP sebelum menambah hard-coded keyword baru, lalu retrain model kategori.

