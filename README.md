# Sakoo Finance Bot

Sakoo Finance Bot adalah personal finance assistant berbasis WhatsApp, Telegram, dan Web Dashboard. Project ini memakai FastAPI, Next.js, PostgreSQL, Redis, Celery, WAHA, Nginx, dan Docker Compose.

## Tech Stack

- Backend: FastAPI Python
- Frontend: Next.js + Tailwind CSS
- Database: PostgreSQL
- Queue/Cache: Redis
- Worker: Celery
- WhatsApp Gateway: WAHA
- OCR: Google Vision API
- Voice Note: Google Speech-to-Text
- PDF Export: WeasyPrint
- Deployment: Docker Compose + Nginx

## Struktur Folder

```text
backend/
  app/
    main.py
    config.py
    database.py
    models.py
    modules/
    workers/
  alembic/
  alembic.ini
  tests/
  requirements.txt
  Dockerfile
frontend/
  app/
  components/
  lib/
  package.json
  Dockerfile
infra/
  docker/docker-compose.yml
  nginx/default.conf
storage/
  receipts/
  voice_notes/
  reports/
  temp/
docs/
```

## Dependency

Dependency minimum untuk menjalankan project dengan Docker:

- Git
- Docker Desktop atau Docker Engine dengan Docker Compose v2
- Port lokal kosong: `80`, `8000`, `3001`, `3002`, `5432`, `6379`

Dependency jika menjalankan service tanpa Docker:

- Python 3.12
- Node.js 22 dan npm
- PostgreSQL 16
- Redis 7
- System library untuk WeasyPrint, Cairo, Pango, libffi, dan libpq

Dependency Python ada di [backend/requirements.txt](backend/requirements.txt). Dependency frontend ada di [frontend/package.json](frontend/package.json).

## Setup Lokal Dengan Docker

Docker adalah cara utama untuk onboarding developer baru karena PostgreSQL, Redis, backend, frontend, Celery, WAHA, dan Nginx sudah disatukan di [infra/docker/docker-compose.yml](infra/docker/docker-compose.yml).

1. Salin file environment dari root project:

```bash
cp .env.example .env
```

PowerShell:

```powershell
Copy-Item .env.example .env
```

2. Isi nilai wajib di `.env`:

```env
POSTGRES_PASSWORD=local_postgres_password
JWT_SECRET=local_jwt_secret_min_32_chars
WAHA_API_KEY=local_waha_api_key_min_32_chars
WAHA_DASHBOARD_USERNAME=admin
WAHA_DASHBOARD_PASSWORD=local_waha_dashboard_password
```

`DATABASE_URL` boleh kosong untuk Docker Compose karena backend dan worker memakai override internal ke service `postgres`.

3. Build dan jalankan service:

```bash
docker compose -f infra/docker/docker-compose.yml up -d --build
```

4. Jalankan migration database:

```bash
docker compose -f infra/docker/docker-compose.yml exec backend alembic upgrade head
```

5. Cek aplikasi:

```bash
curl http://localhost/health
curl http://localhost:8000/health/db
curl http://localhost:8000/health/waha
```

Response health yang diharapkan:

```json
{"status":"ok"}
```

URL lokal:

- Frontend via Nginx: `http://localhost`
- Frontend langsung: `http://localhost:3001`
- Backend langsung: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- Backend via Nginx: `http://localhost/api`
- Health check: `http://localhost/health`
- WAHA: `http://localhost:3002`
- WAHA Dashboard: `http://localhost:3002/dashboard`

## Command Docker Umum

Jalankan semua service:

```bash
docker compose -f infra/docker/docker-compose.yml up -d --build
```

Lihat status service:

```bash
docker compose -f infra/docker/docker-compose.yml ps
```

Lihat log backend:

```bash
docker compose -f infra/docker/docker-compose.yml logs -f backend
```

Lihat log semua service:

```bash
docker compose -f infra/docker/docker-compose.yml logs -f
```

Jalankan migration:

```bash
docker compose -f infra/docker/docker-compose.yml exec backend alembic upgrade head
```

Seed kategori default secara eksplisit:

```bash
docker compose -f infra/docker/docker-compose.yml exec backend python -m app.seeds.categories
```

Masuk shell backend:

```bash
docker compose -f infra/docker/docker-compose.yml exec backend sh
```

Restart service tertentu:

```bash
docker compose -f infra/docker/docker-compose.yml restart backend
docker compose -f infra/docker/docker-compose.yml restart waha
```

Stop container tanpa menghapus volume database/session:

```bash
docker compose -f infra/docker/docker-compose.yml down
```

Stop dan hapus volume lokal PostgreSQL, Redis, dan session WAHA:

```bash
docker compose -f infra/docker/docker-compose.yml down -v
```

## Environment Variable

Daftar variable tersedia di [.env.example](.env.example). Jangan commit file `.env`.

| Variable | Wajib | Dipakai Oleh | Contoh | Catatan |
|---|---|---|---|---|
| `APP_NAME` | Tidak | Backend | `Sakoo Finance Bot` | Nama aplikasi FastAPI. |
| `APP_ENV` | Tidak | Backend | `local` | Nama environment. |
| `API_PREFIX` | Tidak | Backend | `/api` | Prefix router API dashboard. |
| `DEBUG` | Tidak | Backend | `false` | Mode debug FastAPI. |
| `APP_BASE_URL` | Tidak | Backend | `http://localhost` | Base URL publik aplikasi. |
| `FRONTEND_ORIGIN` | Tidak | Backend | `http://localhost:3001` | CORS origin frontend dev. |
| `NEXT_PUBLIC_API_BASE_URL` | Tidak | Frontend | `http://localhost/api` | Base URL API untuk browser. |
| `POSTGRES_USER` | Ya | PostgreSQL | `sakoo` | User database Docker. |
| `POSTGRES_PASSWORD` | Ya | PostgreSQL | `local_postgres_password` | Wajib diisi, tidak boleh kosong saat Docker Compose. |
| `POSTGRES_DB` | Ya | PostgreSQL | `sakoo_finance` | Nama database. |
| `DATABASE_URL` | Manual only | Backend host/Alembic host | `postgresql+psycopg://sakoo:password@localhost:5432/sakoo_finance` | Boleh kosong untuk Docker Compose karena dioverride. Wajib jika backend/Alembic dijalankan dari host. |
| `REDIS_URL` | Tidak | Backend/Celery host | `redis://localhost:6379/0` | Dioverride ke `redis://redis:6379/0` di Docker. |
| `CELERY_BROKER_URL` | Tidak | Celery | `redis://localhost:6379/0` | Jika kosong di config akan memakai Redis URL. |
| `CELERY_RESULT_BACKEND` | Tidak | Celery | `redis://localhost:6379/0` | Backend result Celery. |
| `CELERY_CONCURRENCY` | Tidak | Celery | `1` | Worker concurrency lokal. |
| `JWT_SECRET` | Ya | Backend Auth | `local_jwt_secret_min_32_chars` | Secret JWT. Buat nilai acak dan jangan commit. |
| `JWT_ALGORITHM` | Tidak | Backend Auth | `HS256` | Algoritma JWT. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Tidak | Backend Auth | `60` | Masa berlaku token. |
| `TELEGRAM_BOT_TOKEN` | Tidak | Telegram | `123:abc` | Kosongkan jika belum memakai Telegram. |
| `TELEGRAM_BASE_URL` | Tidak | Backend Telegram | `https://api.telegram.org` | Base URL Telegram Bot API. |
| `TELEGRAM_TIMEOUT_SECONDS` | Tidak | Backend Telegram | `10` | Timeout request backend ke Telegram Bot API. |
| `TELEGRAM_WEBHOOK_URL` | Tidak | Telegram | `http://backend:8000/webhook/telegram` | URL webhook Telegram ke backend. |
| `TELEGRAM_WEBHOOK_SECRET` | Tidak | Backend Telegram | `local_telegram_webhook_secret` | Jika diisi, backend validasi header `X-Telegram-Bot-Api-Secret-Token`. |
| `WAHA_BASE_URL` | Tidak | Backend host | `http://localhost:3002` | Di Docker dioverride menjadi `http://waha:3000`. |
| `WAHA_API_KEY` | Ya | Backend/WAHA | `local_waha_api_key_min_32_chars` | Wajib untuk WAHA API. |
| `WAHA_DASHBOARD_USERNAME` | Ya | WAHA | `admin` | Login dashboard WAHA. |
| `WAHA_DASHBOARD_PASSWORD` | Ya | WAHA | `local_waha_dashboard_password` | Password dashboard WAHA. |
| `WAHA_SESSION_NAME` | Tidak | Backend/WAHA | `default` | Nama session WAHA. |
| `WAHA_TIMEOUT_SECONDS` | Tidak | Backend | `10` | Timeout request backend ke WAHA. |
| `WAHA_WEBHOOK_URL` | Tidak | WAHA | `http://backend:8000/webhook/waha` | URL webhook dari container WAHA ke backend. |
| `WAHA_WEBHOOK_EVENTS` | Tidak | WAHA | `message` | Event WAHA yang dikirim ke backend. |
| `WAHA_WEBHOOK_HMAC_KEY` | Tidak | Backend/WAHA | `local_webhook_secret` | Opsional. Jika diisi, backend validasi HMAC webhook. |
| `GOOGLE_APPLICATION_CREDENTIALS` | Tidak | OCR/STT | `/path/to/key.json` | Diperlukan saat OCR/STT Google dipakai. |
| `OCR_DAILY_LIMIT_PER_USER` | Tidak | Backend OCR | `20` | Batas pemanggilan Google Vision per user per hari. |
| `OCR_RATE_LIMIT_TIMEZONE` | Tidak | Backend OCR | `Asia/Jakarta` | Timezone window harian OCR. |
| `STORAGE_PATH` | Tidak | Backend | `storage` | Lokasi file lokal. Di Docker dioverride ke `/app/storage`. |
| `MEDIA_RECEIPT_MAX_BYTES` | Tidak | Backend | `5242880` | Batas upload struk. Default 5 MB. |
| `MEDIA_DEFAULT_MAX_BYTES` | Tidak | Backend | `10485760` | Batas upload audio dan PDF. Default 10 MB. |

Membuat secret lokal cepat:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Menjalankan Manual Tanpa Docker

Manual setup berguna untuk development backend/frontend saja. Pastikan PostgreSQL dan Redis sudah berjalan di host.

1. Salin `.env` dan isi `DATABASE_URL` host:

```env
DATABASE_URL=postgresql+psycopg://sakoo:local_postgres_password@localhost:5432/sakoo_finance
REDIS_URL=redis://localhost:6379/0
```

2. Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

PowerShell activation:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

3. Frontend:

```bash
cd frontend
npm install
npm run dev
```

Frontend manual tersedia di `http://localhost:3000`. Jika memakai Docker Compose, frontend langsung dipublish di `http://localhost:3001` dan via Nginx di `http://localhost`.

4. Celery worker manual:

```bash
cd backend
celery -A app.workers.celery_app.celery_app worker --loglevel=info --concurrency=1
```

Untuk Docker Compose, jalankan service `celery_worker` bersama backend dan Redis:

```bash
docker compose -f infra/docker/docker-compose.yml up -d --build backend celery_worker redis
```

## Migrasi dan Seed Database

Jalankan migration dari container:

```bash
docker compose -f infra/docker/docker-compose.yml exec backend alembic upgrade head
```

Jalankan migration dari host:

```bash
cd backend
alembic upgrade head
```

Membuat migration baru setelah mengubah model:

```bash
cd backend
alembic revision --autogenerate -m "describe change"
```

Migration awal sudah mengisi kategori default. Jika perlu menjalankan seed ulang secara idempotent:

```bash
cd backend
python -m app.seeds.categories
```

## Endpoint Penting

Health:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/db
curl http://localhost:8000/health/waha
```

Auth dashboard:

```text
POST /api/auth/register
POST /api/auth/login
GET /api/auth/me
```

Transactions:

```text
POST /api/transactions
GET /api/transactions
GET /api/transactions/{id}
PUT /api/transactions/{id}
DELETE /api/transactions/{id}
```

`GET /api/transactions` mendukung query untuk dashboard dan report service:

```text
start_date=YYYY-MM-DD
end_date=YYYY-MM-DD
category_id=1
type=income|expense
limit=50
offset=0
```

Response list berisi `items`, `total`, `limit`, `offset`, dan `has_next`. Sort default adalah transaksi terbaru berdasarkan `transaction_date DESC, id DESC`.

Media:

```text
POST /api/media
GET /api/media/{media_id}/download
```

`POST /api/media` memakai `multipart/form-data` dengan field `file`, `file_type=receipt|audio|pdf`, dan `source`. File disimpan di `STORAGE_PATH/user_{id}/...`, metadata disimpan di `media_files`, dan file tidak disajikan sebagai static public file. Download wajib memakai JWT dan hanya berhasil jika `media_files.user_id` sama dengan user token.

OCR struk:

```text
POST /api/ocr/receipts/{media_id}
GET /api/jobs/{job_id}
```

Endpoint OCR wajib JWT, hanya membaca media receipt milik user yang sedang login, lalu membuat row `jobs` status `queued` dan mengirim task ke Celery/Redis. Response utama adalah HTTP `202`, sehingga request tidak menunggu Google Vision. Worker mengubah status job menjadi `processing`, memanggil Google Vision, menyimpan raw text ke `receipts.ocr_text`, lalu mengubah status menjadi `completed` atau `failed`. Dashboard dapat polling `GET /api/jobs/{job_id}`. Pemanggilan Google Vision dibatasi oleh `OCR_DAILY_LIMIT_PER_USER`; jika limit tercapai backend mengembalikan HTTP `429` dan tidak membuat task. Pemakaian dan limit tercapai dicatat di `bot_logs` dengan `message_type=receipt_ocr`. Parser receipt juga mencoba mengisi `total_amount`, `merchant_name`, `receipt_date`, `confidence`, dan status `processed`, `needs_confirmation`, atau `manual_input_required`. Set `GOOGLE_APPLICATION_CREDENTIALS` ke path file service account Google Cloud di environment lokal/server; credential tidak ditulis di source code.

Webhook WAHA:

```text
POST /webhook/waha
GET /health/waha
```

`GET /health/waha` mengembalikan `200` jika session WAHA berstatus `WORKING`. Jika WAHA logout, stopped, butuh scan QR, atau API WAHA tidak bisa diakses, endpoint mengembalikan `503` dan mencatat warning ke `bot_logs`.

Webhook Telegram:

```text
POST /webhook/telegram
```

`POST /api/auth/login` mengembalikan JWT bearer token. Set `JWT_SECRET` sebelum memakai login dan endpoint private.

## Setup Telegram Bot

Telegram bot memakai endpoint `POST /webhook/telegram`, validasi secret header `X-Telegram-Bot-Api-Secret-Token`, account linking dengan command `hubungkan KODE`, dan transaksi teks dengan source `telegram_text`.

Panduan membuat bot lewat BotFather, set webhook, account linking, test pesan, dan troubleshooting tersedia di [docs/telegram.md](docs/telegram.md).

## Setup WAHA WhatsApp Gateway

WAHA berjalan sebagai service `waha` di Docker Compose dan memakai volume `waha_sessions` agar session WhatsApp tetap tersimpan setelah restart container. Isi `WAHA_API_KEY`, `WAHA_DASHBOARD_USERNAME`, dan `WAHA_DASHBOARD_PASSWORD` di `.env` sebelum menjalankan service.

Panduan scan QR, webhook, account linking, transaksi teks WhatsApp, cek status session, restart session, dan recovery tersedia di [docs/waha.md](docs/waha.md).

WAHA juga mendukung foto struk: user mengirim image, backend mengunduh media, membuat job `receipt_ocr`, menjalankan OCR Google Vision, membalas ringkasan struk, lalu menyimpan transaksi setelah user membalas `YA`. Koreksi total dapat dikirim dengan format `edit total 21000`.

## Troubleshooting

**`variable is required` saat `docker compose up`**

Pastikan `.env` sudah ada di root project dan variable wajib sudah diisi: `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_USER`, `WAHA_API_KEY`, `WAHA_DASHBOARD_USERNAME`, `WAHA_DASHBOARD_PASSWORD`.

**Port sudah dipakai**

Service memakai port `80`, `8000`, `3001`, `3002`, `5432`, dan `6379`. Hentikan service lain atau ubah mapping port di [infra/docker/docker-compose.yml](infra/docker/docker-compose.yml).

**`/health/db` gagal**

Pastikan container `postgres` sehat, migration sudah dijalankan, dan `DATABASE_URL` benar. Cek log:

```bash
docker compose -f infra/docker/docker-compose.yml logs -f postgres backend
```

**Swagger terbuka tetapi endpoint auth error karena JWT**

Isi `JWT_SECRET` di `.env`, restart backend, lalu login ulang.

**Alembic error `Path doesn't exist: alembic`**

Jalankan Alembic dari folder `backend` saat manual:

```bash
cd backend
alembic upgrade head
```

Jika memakai Docker, gunakan:

```bash
docker compose -f infra/docker/docker-compose.yml exec backend alembic upgrade head
```

**WAHA dashboard tidak bisa login atau API ditolak**

Pastikan `WAHA_API_KEY`, `WAHA_DASHBOARD_USERNAME`, dan `WAHA_DASHBOARD_PASSWORD` sama dengan nilai di `.env`, lalu restart service `waha`.

**Webhook WAHA tidak masuk ke backend**

Untuk Docker Compose, `WAHA_WEBHOOK_URL` harus memakai URL internal:

```env
WAHA_WEBHOOK_URL=http://backend:8000/webhook/waha
```

Cek log:

```bash
docker compose -f infra/docker/docker-compose.yml logs -f waha backend
```

**Session WhatsApp hilang setelah restart**

Jangan jalankan `docker compose down -v` jika ingin mempertahankan session. Session disimpan di volume `waha_sessions`.

**`/health/waha` mengembalikan 503**

Session WAHA kemungkinan belum `WORKING`, logout, perlu scan QR ulang, atau API WAHA tidak bisa diakses backend. Cek dashboard WAHA, lalu cek log:

```bash
docker compose -f infra/docker/docker-compose.yml logs -f waha backend
```

Warning juga disimpan ke tabel `bot_logs` dengan `platform=system`, `message_type=waha_health`, dan `status=waha_unhealthy`.

**OCR Google Vision gagal karena credential atau quota**

Pastikan `GOOGLE_APPLICATION_CREDENTIALS` mengarah ke file service account yang tersedia di container/host, Vision API sudah aktif di Google Cloud project, dan service account punya akses Vision API. Jangan commit file JSON credential. Jika response menyebut quota, cek quota Google Vision API di Google Cloud Console.

**Install WeasyPrint manual gagal**

Gunakan Docker untuk menghindari setup native library. Jika tetap manual, install dependency Cairo, Pango, libffi, libpq, dan shared MIME info sesuai OS.

## Catatan Security

- Tidak ada secret atau API key asli di repository.
- Simpan token Telegram, API key WAHA, JWT secret, password database, dan credential Google Cloud di `.env` atau secret manager.
- Jangan commit `.env`, file Google credential, atau file session WhatsApp.
- File upload lokal berada di `storage/` dan isi runtime-nya di-ignore dari Git.
