# Sakoo Finance Bot

Sakoo Finance Bot adalah personal finance assistant berbasis WhatsApp, Telegram, dan Web Dashboard. Setup awal ini menyiapkan fondasi FastAPI, Next.js, PostgreSQL, Redis, Celery, WAHA, Nginx, dan Docker Compose tanpa implementasi fitur bisnis.

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
    modules/
    workers/
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

## Setup Lokal

1. Salin file environment:

```bash
cp .env.example .env
```

2. Isi nilai secret di `.env` untuk environment lokal. Jangan commit `.env`.

## Menjalankan Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
```

Response yang diharapkan:

```json
{"status":"OK"}
```

## Menjalankan Frontend

```bash
cd frontend
npm install
npm run dev
```

Dashboard tersedia di:

```text
http://localhost:3000
```

## Menjalankan Docker Compose

```bash
cp .env.example .env
docker compose -f infra/docker/docker-compose.yml up --build
```

Endpoint utama:

- Frontend via Nginx: `http://localhost`
- Backend langsung: `http://localhost:8000`
- Backend via Nginx: `http://localhost/api`
- Health check: `http://localhost/health`
- WAHA: `http://localhost:3002`

## Catatan Security

- Tidak ada secret atau API key asli di repository.
- Simpan token Telegram, API key WAHA, JWT secret, dan credential Google Cloud di `.env` atau secret manager.
- File upload lokal berada di `storage/` dan isi runtime-nya di-ignore dari Git.
