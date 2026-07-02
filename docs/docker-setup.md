# Setup Docker Sakoo Finance Bot

Dokumen ini menjelaskan cara menjalankan Sakoo Finance Bot dengan Docker Compose sampai backend, frontend, database, worker, WAHA, dan Nginx berjalan normal.

## Panduan Cepat

Bagian ini cukup untuk menjalankan project dari nol. Detail lengkap ada di bagian bawah.

### Pilihan 1: Jalan Lokal Saja

Pakai cara ini kalau hanya ingin membuka dashboard di laptop sendiri.

1. Buat file `.env`.

```bash
cp .env.example .env
```

2. Isi minimal ini di `.env`.

```env
APP_BASE_URL=http://localhost:8080
NEXT_PUBLIC_API_BASE_URL=http://localhost:8080/api
NGINX_HTTP_PORT=8080

POSTGRES_USER=sakoo
POSTGRES_PASSWORD=password_lokal
POSTGRES_DB=sakoo_finance

JWT_SECRET=secret_panjang_minimal_32_karakter

WAHA_API_KEY=apikey_waha_lokal
WAHA_DASHBOARD_USERNAME=admin
WAHA_DASHBOARD_PASSWORD=password_waha_lokal
WAHA_WEBHOOK_URL=http://backend:8000/webhook/waha
```

3. Jalankan Docker dari root project.

```bash
docker compose -f infra/docker/docker-compose.yml --env-file .env up -d --build
```

4. Cek status.

```bash
docker ps
curl http://localhost:8080/health
```

Berhasil kalau:

```text
postgres  Up (healthy)
redis     Up (healthy)
backend   Up
frontend  Up
nginx     Up
```

Dan health:

```json
{"status":"ok"}
```

5. Buka dashboard.

```text
http://localhost:8080
```

### Pilihan 2: Jalan Lokal Tapi Bisa Diakses Telegram/Internet

Pakai cara ini kalau bot Telegram perlu menerima webhook dari internet.

1. Jalankan Docker lokal dulu.

```bash
docker compose -f infra/docker/docker-compose.yml --env-file .env up -d --build
curl http://localhost:8080/health
```

2. Jalankan ngrok ke port Nginx.

```bash
ngrok http 8080
```

Misal URL dari ngrok:

```text
https://abc-123.ngrok-free.app
```

3. Ubah `.env`.

```env
APP_BASE_URL=https://abc-123.ngrok-free.app
NEXT_PUBLIC_API_BASE_URL=https://abc-123.ngrok-free.app/api
TELEGRAM_WEBHOOK_URL=https://abc-123.ngrok-free.app/webhook/telegram
```

Biarkan WAHA tetap internal:

```env
WAHA_WEBHOOK_URL=http://backend:8000/webhook/waha
```

4. Rebuild service yang membaca env.

```bash
docker compose -f infra/docker/docker-compose.yml --env-file .env up -d --build backend frontend nginx
```

5. Set webhook Telegram.

```bash
curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  -d "url=$TELEGRAM_WEBHOOK_URL" \
  -d "secret_token=$TELEGRAM_WEBHOOK_SECRET" \
  -d "drop_pending_updates=true" \
  -d "allowed_updates=[\"message\",\"callback_query\"]"
```

6. Cek webhook.

```bash
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getWebhookInfo"
```

Berhasil kalau `url` berisi URL ngrok terbaru dan `pending_update_count` tidak terus naik.

### Kapan Harus Rebuild?

Gunakan rule sederhana ini:

| Perubahan | Command |
|---|---|
| Ubah kode backend | `docker compose -f infra/docker/docker-compose.yml --env-file .env up -d --build backend celery_worker` |
| Ubah kode frontend | `docker compose -f infra/docker/docker-compose.yml --env-file .env up -d --build frontend nginx` |
| Ubah `.env` backend | `docker compose -f infra/docker/docker-compose.yml --env-file .env up -d --build backend celery_worker` |
| Ubah `NEXT_PUBLIC_API_BASE_URL` | `docker compose -f infra/docker/docker-compose.yml --env-file .env up -d --build frontend nginx` |
| URL ngrok berubah | update `.env`, rebuild `backend frontend nginx`, lalu set webhook Telegram ulang |

### Command Yang Paling Sering Dipakai

```bash
# Jalankan semua
docker compose -f infra/docker/docker-compose.yml --env-file .env up -d --build

# Cek container
docker ps

# Cek backend via nginx
curl http://localhost:8080/health

# Lihat log backend
docker compose -f infra/docker/docker-compose.yml --env-file .env logs -f backend

# Lihat log frontend
docker compose -f infra/docker/docker-compose.yml --env-file .env logs -f frontend

# Stop tanpa hapus data
docker compose -f infra/docker/docker-compose.yml --env-file .env down
```

### Alur Paling Penting

```text
User buka browser
-> http://localhost:8080
-> nginx
-> frontend
-> frontend memanggil http://localhost:8080/api
-> nginx meneruskan /api ke backend
-> backend memakai postgres, redis, celery worker
```

Kalau pakai ngrok:

```text
Telegram
-> https://URL-NGROK/webhook/telegram
-> ngrok
-> localhost:8080
-> nginx
-> backend
```

## Ringkasan Service

File utama Docker ada di:

```text
infra/docker/docker-compose.yml
```

Service yang dijalankan:

| Service | Fungsi | Port Host |
|---|---|---|
| `nginx` | Reverse proxy frontend, backend API, health, webhook | `8080` default |
| `frontend` | Next.js dashboard | `3001` |
| `backend` | FastAPI API, webhook, migration Alembic otomatis | `8000` |
| `celery_worker` | Worker OCR, STT, export PDF, background jobs | internal |
| `postgres` | Database PostgreSQL | `5432` |
| `redis` | Broker/cache Celery | `6379` |
| `waha` | WhatsApp gateway | `3002` |

Flow integrasi lokal:

```text
Browser -> http://localhost:8080 -> nginx
nginx /       -> frontend:3000
nginx /api    -> backend:8000
nginx /health -> backend:8000/health
nginx /webhook -> backend:8000/webhook
frontend -> NEXT_PUBLIC_API_BASE_URL=http://localhost:8080/api
backend -> postgres, redis, waha
celery_worker -> postgres, redis, waha, storage
```

## Prasyarat

Pastikan sudah tersedia:

- Docker Desktop atau Docker Engine.
- Docker Compose v2.
- Port lokal kosong: `8080`, `8000`, `3001`, `3002`, `5432`, `6379`.
- File `.env` berada di root project.

Cek Docker:

```bash
docker --version
docker compose version
```

## Setup `.env`

Dari root project:

```bash
cp .env.example .env
```

PowerShell:

```powershell
Copy-Item .env.example .env
```

Isi minimal variable ini:

```env
APP_BASE_URL=http://localhost:8080
FRONTEND_ORIGIN=http://localhost:3001
NEXT_PUBLIC_API_BASE_URL=http://localhost:8080/api
NGINX_HTTP_PORT=8080

POSTGRES_USER=sakoo
POSTGRES_PASSWORD=isi_password_lokal
POSTGRES_DB=sakoo_finance
DATABASE_URL=

JWT_SECRET=isi_secret_panjang_minimal_32_karakter

WAHA_API_KEY=isi_waha_api_key_lokal
WAHA_DASHBOARD_USERNAME=admin
WAHA_DASHBOARD_PASSWORD=isi_password_dashboard_waha
WAHA_SESSION_NAME=default
WAHA_WEBHOOK_URL=http://backend:8000/webhook/waha
```

Catatan:

- `DATABASE_URL` boleh kosong saat memakai Docker Compose karena compose akan override ke hostname internal `postgres`.
- `NEXT_PUBLIC_API_BASE_URL` harus mengarah ke URL yang bisa diakses browser. Untuk Nginx lokal gunakan `http://localhost:8080/api`.
- Jangan commit file `.env`.

Opsional LLM:

```env
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=isi_openrouter_key
OPENROUTER_MODEL=deepseek/deepseek-chat
LLM_MAX_REQUEST_PER_USER_PER_DAY=20
```

Jika memakai Gemini tetapi quota sering kena limit, gunakan OpenRouter dulu:

```env
LLM_PROVIDER=openrouter,gemini
```

## Menjalankan Docker

Dari root project:

```bash
docker compose -f infra/docker/docker-compose.yml --env-file .env up -d --build
```

Jika hanya ingin rebuild backend dan worker:

```bash
docker compose -f infra/docker/docker-compose.yml --env-file .env up -d --build backend celery_worker
```

Backend otomatis menjalankan:

```text
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Cek Status Container

Gunakan:

```bash
docker compose -f infra/docker/docker-compose.yml --env-file .env ps
```

Atau:

```bash
docker ps
```

Status yang diharapkan:

```text
docker-backend-1         Up
docker-celery_worker-1   Up
docker-frontend-1        Up
docker-nginx-1           Up
docker-waha-1            Up
docker-redis-1           Up (healthy)
docker-postgres-1        Up (healthy)
```

Jika `postgres` atau `redis` belum `healthy`, tunggu beberapa detik lalu cek ulang.

## Cek Health Backend dan Proxy

Tes dari host:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/db
curl http://localhost:8080/health
```

Response normal:

```json
{"status":"ok"}
```

Tes frontend:

```bash
curl -I http://localhost:3001
curl -I http://localhost:8080
```

Tes API via Nginx:

```bash
curl http://localhost:8080/api/auth/me
```

Jika belum login, endpoint private boleh mengembalikan `401`. Itu berarti routing API sudah sampai ke backend.

## URL Lokal

| URL | Keterangan |
|---|---|
| `http://localhost:8080` | Akses utama lewat Nginx |
| `http://localhost:8080/api` | Backend API lewat Nginx |
| `http://localhost:8080/health` | Health lewat Nginx |
| `http://localhost:3001` | Frontend langsung |
| `http://localhost:8000` | Backend langsung |
| `http://localhost:8000/docs` | Swagger backend |
| `http://localhost:3002` | WAHA |
| `http://localhost:3002/dashboard` | WAHA dashboard |

Rekomendasi untuk penggunaan lokal: buka dashboard dari `http://localhost:8080`, bukan `3001`, supaya alur frontend dan backend sama-sama lewat Nginx.

## Integrasi Backend dan Frontend

Frontend membaca API base URL dari:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8080/api
```

Karena variable `NEXT_PUBLIC_*` dibaca saat build frontend, setelah mengubah nilai ini wajib rebuild service frontend:

```bash
docker compose -f infra/docker/docker-compose.yml --env-file .env up -d --build frontend nginx
```

Validasi dari browser:

1. Buka `http://localhost:8080`.
2. Buka DevTools browser.
3. Login/register dari dashboard.
4. Pastikan request API mengarah ke `http://localhost:8080/api/...`.
5. Jika request mengarah ke port salah, cek ulang `NEXT_PUBLIC_API_BASE_URL` dan rebuild frontend.

## Tunneling Lokal Dengan Ngrok

Tunneling dipakai ketika service lokal harus diakses dari internet, misalnya:

- Telegram webhook.
- Testing frontend dari device lain.
- Testing callback/webhook eksternal.
- Demo lokal tanpa deploy server.

Rekomendasi: tunnel ke port Nginx, yaitu `8080`. Dengan cara ini frontend, backend API, health check, dan webhook tetap memakai satu public base URL.

### 1. Pastikan Docker Berjalan

Jalankan dari root project:

```bash
docker compose -f infra/docker/docker-compose.yml --env-file .env up -d --build
curl http://localhost:8080/health
```

Health harus mengembalikan:

```json
{"status":"ok"}
```

### 2. Jalankan Ngrok

Install dan login ngrok sesuai dokumentasi akun ngrok kamu, lalu jalankan:

```bash
ngrok http 8080
```

Ngrok akan memberi URL publik seperti:

```text
https://abc-123.ngrok-free.app
```

Gunakan URL HTTPS tersebut sebagai base URL publik.

### 3. Update `.env`

Ganti nilai berikut di `.env`:

```env
APP_BASE_URL=https://abc-123.ngrok-free.app
NEXT_PUBLIC_API_BASE_URL=https://abc-123.ngrok-free.app/api
TELEGRAM_WEBHOOK_URL=https://abc-123.ngrok-free.app/webhook/telegram
```

Untuk WAHA lokal, biarkan webhook internal tetap seperti ini:

```env
WAHA_WEBHOOK_URL=http://backend:8000/webhook/waha
```

Alasannya: container WAHA dan backend berada di network Docker yang sama, jadi tidak perlu lewat ngrok untuk komunikasi WAHA ke backend lokal.

### 4. Rebuild Service Yang Membaca Env

Karena `NEXT_PUBLIC_API_BASE_URL` dibaca saat build frontend, rebuild frontend. Backend juga perlu restart agar `APP_BASE_URL` dan `TELEGRAM_WEBHOOK_URL` terbaca.

```bash
docker compose -f infra/docker/docker-compose.yml --env-file .env up -d --build backend frontend nginx
```

Jika worker juga bergantung pada env terbaru, rebuild worker:

```bash
docker compose -f infra/docker/docker-compose.yml --env-file .env up -d --build celery_worker
```

### 5. Cek Public URL

Tes dari host:

```bash
curl https://abc-123.ngrok-free.app/health
curl -I https://abc-123.ngrok-free.app
```

Jika `health` mengembalikan `ok`, ngrok sudah tersambung ke Nginx lokal.

### 6. Set Webhook Telegram

Pastikan `.env` punya:

```env
TELEGRAM_BOT_TOKEN=isi_token_bot
TELEGRAM_WEBHOOK_SECRET=isi_secret_webhook
TELEGRAM_WEBHOOK_URL=https://abc-123.ngrok-free.app/webhook/telegram
```

Set webhook:

```bash
curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  -d "url=$TELEGRAM_WEBHOOK_URL" \
  -d "secret_token=$TELEGRAM_WEBHOOK_SECRET" \
  -d "drop_pending_updates=true" \
  -d "allowed_updates=[\"message\",\"callback_query\"]"
```

Cek status webhook:

```bash
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getWebhookInfo"
```

Yang diharapkan:

```json
{
  "ok": true,
  "result": {
    "url": "https://abc-123.ngrok-free.app/webhook/telegram",
    "pending_update_count": 0
  }
}
```

Jika `allowed_updates` hanya berisi `["message"]`, tombol inline Telegram tidak akan mengirim callback ke backend. Set ulang webhook dengan `callback_query` seperti command di atas.

### 7. Test Telegram

Kirim pesan ke bot:

```text
/start
```

Lalu test transaksi natural:

```text
beli makan 20 ribu
```

Cek log backend:

```bash
docker compose -f infra/docker/docker-compose.yml --env-file .env logs -f backend
```

### 8. Saat URL Ngrok Berubah

Free ngrok biasanya memberi URL baru setiap restart. Jika URL berubah:

1. Update `APP_BASE_URL`.
2. Update `NEXT_PUBLIC_API_BASE_URL`.
3. Update `TELEGRAM_WEBHOOK_URL`.
4. Rebuild `backend frontend nginx`.
5. Jalankan ulang `setWebhook`.

Command ringkas:

```bash
docker compose -f infra/docker/docker-compose.yml --env-file .env up -d --build backend frontend nginx
curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  -d "url=$TELEGRAM_WEBHOOK_URL" \
  -d "secret_token=$TELEGRAM_WEBHOOK_SECRET" \
  -d "drop_pending_updates=true" \
  -d "allowed_updates=[\"message\",\"callback_query\"]"
```

### 9. Checklist Ngrok Sukses

- `ngrok http 8080` aktif dan menampilkan URL HTTPS.
- `curl https://URL-NGROK/health` mengembalikan `{"status":"ok"}`.
- `.env` memakai URL ngrok yang sama untuk `APP_BASE_URL` dan `TELEGRAM_WEBHOOK_URL`.
- `NEXT_PUBLIC_API_BASE_URL` memakai `https://URL-NGROK/api`.
- Backend dan frontend sudah di-rebuild setelah env berubah.
- `getWebhookInfo` Telegram menampilkan URL ngrok terbaru.
- `allowed_updates` mencakup `message` dan `callback_query`.
- `/start` di Telegram mendapat response dari bot.

## Command Operasional

Lihat log backend:

```bash
docker compose -f infra/docker/docker-compose.yml --env-file .env logs -f backend
```

Lihat log frontend:

```bash
docker compose -f infra/docker/docker-compose.yml --env-file .env logs -f frontend
```

Lihat log Nginx:

```bash
docker compose -f infra/docker/docker-compose.yml --env-file .env logs -f nginx
```

Lihat log worker:

```bash
docker compose -f infra/docker/docker-compose.yml --env-file .env logs -f celery_worker
```

Lihat log semua service:

```bash
docker compose -f infra/docker/docker-compose.yml --env-file .env logs -f
```

Restart service tertentu:

```bash
docker compose -f infra/docker/docker-compose.yml --env-file .env restart backend
docker compose -f infra/docker/docker-compose.yml --env-file .env restart frontend
docker compose -f infra/docker/docker-compose.yml --env-file .env restart nginx
```

Masuk shell backend:

```bash
docker compose -f infra/docker/docker-compose.yml --env-file .env exec backend sh
```

Jalankan migration manual:

```bash
docker compose -f infra/docker/docker-compose.yml --env-file .env exec backend alembic upgrade head
```

Jalankan test backend di container:

```bash
docker compose -f infra/docker/docker-compose.yml --env-file .env exec backend pytest
```

Stop container tanpa hapus data:

```bash
docker compose -f infra/docker/docker-compose.yml --env-file .env down
```

Stop dan hapus volume database/redis/session WAHA:

```bash
docker compose -f infra/docker/docker-compose.yml --env-file .env down -v
```

Gunakan `down -v` hanya jika memang ingin reset data lokal.

## Checklist Sukses

Docker dianggap berjalan sukses jika semua poin ini terpenuhi:

- `docker ps` menampilkan semua service utama `Up`.
- `postgres` dan `redis` berstatus `healthy`.
- `curl http://localhost:8000/health` mengembalikan `{"status":"ok"}`.
- `curl http://localhost:8000/health/db` mengembalikan status database sehat.
- `curl http://localhost:8080/health` mengembalikan `{"status":"ok"}` dari Nginx.
- `http://localhost:8080` membuka frontend.
- Request frontend mengarah ke `http://localhost:8080/api`.
- `http://localhost:8000/docs` membuka Swagger.
- Log backend tidak loop error migration atau database connection.
- Log frontend tidak error build/runtime.

## Troubleshooting

### `no configuration file provided: not found`

Command dijalankan dari folder yang salah atau tidak menyertakan file compose. Dari root project jalankan:

```bash
docker compose -f infra/docker/docker-compose.yml --env-file .env up -d --build
```

Jika sedang berada di folder `backend`, kembali dulu:

```bash
cd ..
```

### `POSTGRES_PASSWORD is required`

Isi variable wajib di `.env`:

```env
POSTGRES_USER=sakoo
POSTGRES_PASSWORD=isi_password_lokal
POSTGRES_DB=sakoo_finance
```

Lalu recreate:

```bash
docker compose -f infra/docker/docker-compose.yml --env-file .env up -d --build
```

### Backend gagal connect database

Cek status:

```bash
docker compose -f infra/docker/docker-compose.yml --env-file .env ps postgres backend
```

Cek log:

```bash
docker compose -f infra/docker/docker-compose.yml --env-file .env logs -f postgres backend
```

Pastikan backend di Docker memakai hostname `postgres`, bukan `localhost`. Compose sudah mengatur ini otomatis lewat `DATABASE_URL` internal.

### Frontend tidak bisa hit backend

Cek `.env`:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8080/api
```

Rebuild frontend:

```bash
docker compose -f infra/docker/docker-compose.yml --env-file .env up -d --build frontend nginx
```

Cek request di DevTools browser. Jika masih ke URL lama, browser bisa jadi menyimpan cache build. Hard refresh halaman.

### `curl http://localhost:8080/health` 502 Bad Gateway

Nginx tidak bisa menjangkau backend. Cek:

```bash
docker compose -f infra/docker/docker-compose.yml --env-file .env ps backend nginx
docker compose -f infra/docker/docker-compose.yml --env-file .env logs -f backend nginx
```

Biasanya backend belum selesai migration/startup atau crash karena env/database.

### `curl http://localhost:8000/health` berhasil tetapi `8080/health` gagal

Backend sehat, tapi Nginx bermasalah. Restart Nginx:

```bash
docker compose -f infra/docker/docker-compose.yml --env-file .env restart nginx
```

Lalu cek log Nginx.

### Port sudah dipakai

Cek container/service yang memakai port:

```bash
docker ps
```

Ubah port Nginx di `.env`:

```env
NGINX_HTTP_PORT=8081
NEXT_PUBLIC_API_BASE_URL=http://localhost:8081/api
APP_BASE_URL=http://localhost:8081
```

Lalu rebuild frontend dan Nginx:

```bash
docker compose -f infra/docker/docker-compose.yml --env-file .env up -d --build frontend nginx
```

### Perubahan `.env` tidak terbaca

Docker container tidak otomatis mengambil perubahan `.env`. Recreate service:

```bash
docker compose -f infra/docker/docker-compose.yml --env-file .env up -d --build backend celery_worker frontend nginx
```

Cek env yang terbaca container tanpa menampilkan secret:

```bash
docker exec -it docker-backend-1 python -c "from app.config import get_settings; s=get_settings(); print('app_base_url=', s.app_base_url); print('llm_provider=', s.llm_provider); print('telegram set=', bool(s.telegram_bot_token)); print('openrouter set=', bool(s.openrouter_api_key))"
```

### Telegram webhook dengan Ngrok

Lihat bagian [Tunneling Lokal Dengan Ngrok](#tunneling-lokal-dengan-ngrok) untuk langkah lengkap. Intinya, `TELEGRAM_WEBHOOK_URL` harus memakai URL publik:

```env
APP_BASE_URL=https://domain-ngrok.ngrok-free.app
NEXT_PUBLIC_API_BASE_URL=https://domain-ngrok.ngrok-free.app/api
TELEGRAM_WEBHOOK_URL=https://domain-ngrok.ngrok-free.app/webhook/telegram
```

Recreate backend dan frontend:

```bash
docker compose -f infra/docker/docker-compose.yml --env-file .env up -d --build backend frontend nginx
```

Set webhook:

```bash
curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  -d "url=$TELEGRAM_WEBHOOK_URL" \
  -d "secret_token=$TELEGRAM_WEBHOOK_SECRET" \
  -d "drop_pending_updates=true" \
  -d "allowed_updates=[\"message\",\"callback_query\"]"
```

Pastikan Ngrok mengarah ke port Nginx, misalnya `8080`, bukan langsung ke port yang salah.

### Gemini/OpenRouter LLM

Jika Gemini mengembalikan `429`, itu quota/rate limit. Untuk development lokal, gunakan OpenRouter sebagai provider utama:

```env
LLM_PROVIDER=openrouter
```

Recreate backend:

```bash
docker compose -f infra/docker/docker-compose.yml --env-file .env up -d --build backend celery_worker
```

Cek provider yang terbaca:

```bash
docker exec -it docker-backend-1 python -c "from app.config import get_settings; from app.modules.llm.llm_router import get_llm_providers; s=get_settings(); print('provider=', s.llm_provider); print('chain=', [p.provider_name for p in get_llm_providers(s)])"
```

Jangan menampilkan API key di terminal atau screenshot.

## Quick Start

Versi singkat dari nol:

```bash
cp .env.example .env
nano .env
docker compose -f infra/docker/docker-compose.yml --env-file .env up -d --build
docker compose -f infra/docker/docker-compose.yml --env-file .env ps
curl http://localhost:8080/health
```

Buka:

```text
http://localhost:8080
```

Jika frontend terbuka dan health `ok`, Docker setup dasar sudah berhasil.
