# Deployment Ubuntu Server Dengan Cloudflare Tunnel dan GitHub Actions

Dokumen ini menjelaskan cara menjadikan laptop Ubuntu sebagai server untuk project Sakoo Finance Bot, memakai Cloudflare Tunnel untuk akses publik, dan GitHub Actions self-hosted runner untuk CI/CD.

## Ringkasan Arsitektur

```text
Developer push ke branch main
        |
        v
GitHub Actions CI
        |
        v
GitHub Actions Deploy
self-hosted runner di laptop Ubuntu
        |
        v
Docker Compose rebuild dan restart container
        |
        v
Nginx container di localhost:8080
        |
        v
Cloudflare Tunnel
        |
        v
https://app.domainkamu.com
```

Cloudflare di sini bukan tempat menjalankan aplikasi. Aplikasi tetap berjalan di laptop Ubuntu. Cloudflare hanya menjadi jalur akses publik ke laptop tersebut.

Tidak perlu Cloudflare Pages untuk project ini karena aplikasi memakai FastAPI, Next.js server, PostgreSQL, Redis, Celery, WAHA, dan Docker Compose.

## Komponen Yang Dipakai

- Laptop Ubuntu sebagai server.
- Docker dan Docker Compose untuk menjalankan service aplikasi.
- GitHub Actions CI yang sudah ada di `.github/workflows/ci.yml`.
- GitHub Actions self-hosted runner di laptop Ubuntu untuk deploy.
- Workflow deploy di `.github/workflows/deploy.yml`.
- Cloudflare Tunnel untuk membuka `localhost:8080` ke domain publik.
- GitHub Secrets untuk menyimpan `.env` production.

## Prasyarat

Pastikan tersedia:

- Laptop Ubuntu yang selalu menyala.
- Koneksi internet stabil.
- Repository GitHub project ini.
- Domain yang sudah ada di Cloudflare.
- Akun GitHub dengan akses admin ke repository.
- Akun Cloudflare dengan akses ke domain.

Catatan penting:

- Laptop jangan masuk mode sleep.
- Repo sebaiknya private jika memakai self-hosted runner.
- Jangan commit `.env`, credential Google, atau secret lain ke repository.

## File Workflow Deploy

Workflow deploy berada di:

```text
.github/workflows/deploy.yml
```

Workflow tersebut memakai runner dengan label:

```yaml
runs-on:
  - self-hosted
  - Linux
  - sakoo-prod
```

Artinya, saat mendaftarkan runner di laptop Ubuntu, runner harus punya label `sakoo-prod`.

Deploy akan berjalan ketika:

- CI untuk branch `main` selesai dengan status sukses.
- Workflow dijalankan manual lewat tab GitHub Actions.

Perintah utama yang dijalankan workflow:

```bash
docker compose -f infra/docker/docker-compose.yml up -d --build --remove-orphans
```

Setelah deploy, workflow mengecek:

```text
http://127.0.0.1:8080/health
```

Jika `NGINX_HTTP_PORT` di `.env` berbeda, workflow akan mengikuti nilai tersebut.

## 1. Setup Server Ubuntu

Jalankan perintah berikut di laptop Ubuntu.

Update package:

```bash
sudo apt update
sudo apt install -y git curl ca-certificates
```

Install Docker:

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker
```

Cek Docker:

```bash
docker --version
docker compose version
```

Jika `docker compose version` berhasil, Docker sudah siap.

## 2. Setup Cloudflare Tunnel

Install `cloudflared` di Ubuntu:

```bash
sudo mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main" | sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt update
sudo apt install -y cloudflared
```

Buat tunnel dari Cloudflare dashboard:

```text
Cloudflare Dashboard
> Zero Trust
> Networks
> Tunnels
> Create a tunnel
> Cloudflared
```

Pilih Debian/Ubuntu, lalu Cloudflare akan memberi command seperti ini:

```bash
sudo cloudflared service install TOKEN_DARI_CLOUDFLARE
```

Jalankan command tersebut di laptop Ubuntu.

Cek service:

```bash
sudo systemctl status cloudflared
```

Tambahkan public hostname di Cloudflare Tunnel:

```text
Hostname: app.domainkamu.com
Service type: HTTP
Service URL: localhost:8080
```

Dengan konfigurasi ini, request ke:

```text
https://app.domainkamu.com
```

akan diteruskan ke:

```text
http://localhost:8080
```

di laptop Ubuntu.

## 3. Setup GitHub Self-hosted Runner

Di GitHub repository:

```text
Settings
> Actions
> Runners
> New self-hosted runner
> Linux
```

Ikuti perintah yang diberikan GitHub. Bentuknya kurang lebih seperti ini:

```bash
mkdir actions-runner
cd actions-runner
curl -o actions-runner-linux-x64.tar.gz -L URL_DARI_GITHUB
tar xzf ./actions-runner-linux-x64.tar.gz
./config.sh --url https://github.com/OWNER/REPO --token TOKEN_DARI_GITHUB --labels sakoo-prod
```

Token runner dari GitHub biasanya hanya berlaku sekitar 1 jam. Jika token expired, buat runner baru dari GitHub UI.

Jalankan runner sebagai service:

```bash
sudo ./svc.sh install $USER
sudo ./svc.sh start
sudo ./svc.sh status
```

Pastikan runner terlihat online di:

```text
Settings > Actions > Runners
```

## 4. Buat Environment Production

Di laptop development atau mesin yang punya `gh` CLI, buat file `.env.production`:

```powershell
Copy-Item .env.example .env.production
notepad .env.production
```

Jika memakai Linux/macOS:

```bash
cp .env.example .env.production
nano .env.production
```

Contoh nilai penting:

```env
APP_NAME=Sakoo Finance Bot
APP_ENV=production
API_PREFIX=/api
DEBUG=false
APP_BASE_URL=https://app.domainkamu.com
FRONTEND_ORIGIN=https://app.domainkamu.com
NEXT_PUBLIC_API_BASE_URL=https://app.domainkamu.com/api
NGINX_HTTP_PORT=8080

POSTGRES_USER=sakoo
POSTGRES_PASSWORD=ganti_dengan_password_kuat
POSTGRES_DB=sakoo_finance
DATABASE_URL=

REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
CELERY_CONCURRENCY=1

JWT_SECRET=ganti_dengan_secret_minimal_32_karakter
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
ACCOUNT_LINKING_CODE_TTL_MINUTES=10

TELEGRAM_BOT_TOKEN=
TELEGRAM_BASE_URL=https://api.telegram.org
TELEGRAM_TIMEOUT_SECONDS=10
TELEGRAM_WEBHOOK_URL=https://app.domainkamu.com/webhook/telegram
TELEGRAM_WEBHOOK_SECRET=ganti_dengan_secret_telegram
TELEGRAM_REGISTER_COMMANDS_ON_STARTUP=false

WAHA_BASE_URL=http://localhost:3002
WAHA_API_KEY=ganti_dengan_api_key_waha
WAHA_DASHBOARD_USERNAME=admin
WAHA_DASHBOARD_PASSWORD=ganti_dengan_password_dashboard_waha
WAHA_SESSION_NAME=default
WAHA_TIMEOUT_SECONDS=10
WAHA_WEBHOOK_URL=http://backend:8000/webhook/waha
WAHA_WEBHOOK_EVENTS=message
WAHA_WEBHOOK_HMAC_KEY=ganti_dengan_secret_hmac_waha

GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/google-service-account.json
OCR_DAILY_LIMIT_PER_USER=20
OCR_RATE_LIMIT_TIMEZONE=Asia/Jakarta
STT_LANGUAGE_CODE=id-ID
STT_MAX_DURATION_SECONDS=30
STT_ENABLE_AUTOMATIC_PUNCTUATION=true
STORAGE_PATH=storage
MEDIA_RECEIPT_MAX_BYTES=5242880
MEDIA_DEFAULT_MAX_BYTES=10485760

LLM_PROVIDER=none
LLM_TIMEOUT_SECONDS=15
LLM_MAX_REQUEST_PER_USER_PER_DAY=20
BOT_REPLY_STYLE=friendly
```

Buat secret acak:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Untuk Windows PowerShell:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Variable wajib untuk deploy:

- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- `JWT_SECRET`
- `WAHA_API_KEY`
- `WAHA_DASHBOARD_USERNAME`
- `WAHA_DASHBOARD_PASSWORD`

## 5. Simpan Environment Ke GitHub Secrets

Login ke GitHub CLI:

```bash
gh auth login
```

Simpan `.env.production` sebagai secret:

```bash
gh secret set PRODUCTION_ENV < .env.production
```

Jika menjalankan dari PowerShell:

```powershell
Get-Content .env.production -Raw | gh secret set PRODUCTION_ENV
```

Jika memakai Google Vision atau Google Speech-to-Text, simpan credential JSON:

```bash
gh secret set GOOGLE_CREDENTIALS_JSON < credentials/google-service-account.json
```

PowerShell:

```powershell
Get-Content credentials\google-service-account.json -Raw | gh secret set GOOGLE_CREDENTIALS_JSON
```

Workflow deploy akan menulis:

```text
.env
credentials/google-service-account.json
```

di workspace runner sebelum menjalankan Docker Compose.

## 6. Commit dan Push Workflow

Dari folder project:

```bash
git add .github/workflows/deploy.yml docs/ubuntu-cloudflare-cicd.md
git commit -m "Add Ubuntu Cloudflare deployment docs"
git push origin main
```

Jika Git menolak karena `dubious ownership`, jalankan:

```bash
git config --global --add safe.directory "D:/Pemrograman/Sakoo bot"
```

Untuk path Linux, sesuaikan dengan lokasi repository.

## 7. Deploy Pertama

Ada dua cara.

Cara otomatis:

```text
Push ke branch main
> CI berjalan
> jika CI sukses, Deploy berjalan otomatis
```

Cara manual:

```text
GitHub repository
> Actions
> Deploy
> Run workflow
```

Saat deploy sukses, cek dari laptop Ubuntu:

```bash
curl -fsS http://127.0.0.1:8080/health
```

Cek dari internet:

```bash
curl -fsS https://app.domainkamu.com/health
```

## 8. Setup Telegram Webhook

Jika Telegram dipakai, set webhook ke domain publik.

Contoh:

```bash
curl "https://api.telegram.org/botBOT_TOKEN/setWebhook" \
  -d "url=https://app.domainkamu.com/webhook/telegram" \
  -d "secret_token=TELEGRAM_WEBHOOK_SECRET"
```

Ganti:

- `BOT_TOKEN` dengan token bot Telegram.
- `TELEGRAM_WEBHOOK_SECRET` dengan nilai di `.env.production`.

## 9. Setup WAHA WhatsApp

WAHA berjalan di Docker container dan dashboard-nya tersedia di port host `3002`.

Dari laptop Ubuntu:

```text
http://localhost:3002/dashboard
```

Jika ingin akses dashboard WAHA dari browser laptop lain di jaringan lokal:

```text
http://IP_LAPTOP_UBUNTU:3002/dashboard
```

Login memakai:

- `WAHA_DASHBOARD_USERNAME`
- `WAHA_DASHBOARD_PASSWORD`

Webhook WAHA tetap memakai URL internal Docker:

```env
WAHA_WEBHOOK_URL=http://backend:8000/webhook/waha
```

Jangan ubah ke domain publik kecuali WAHA dijalankan di luar Docker network project.

## 10. Command Operasional Di Server

Cek container:

```bash
docker compose -f infra/docker/docker-compose.yml ps
```

Lihat log semua service:

```bash
docker compose -f infra/docker/docker-compose.yml logs -f
```

Lihat log backend:

```bash
docker compose -f infra/docker/docker-compose.yml logs -f backend
```

Restart backend:

```bash
docker compose -f infra/docker/docker-compose.yml restart backend
```

Restart semua service:

```bash
docker compose -f infra/docker/docker-compose.yml restart
```

Stop service tanpa menghapus data:

```bash
docker compose -f infra/docker/docker-compose.yml down
```

Jangan jalankan ini di production kecuali benar-benar ingin menghapus database dan session WAHA:

```bash
docker compose -f infra/docker/docker-compose.yml down -v
```

## 11. Troubleshooting

### Deploy tidak jalan

Cek runner online:

```text
GitHub repository
> Settings
> Actions
> Runners
```

Pastikan label runner mengandung:

```text
sakoo-prod
```

Jika label berbeda, samakan label runner atau ubah `.github/workflows/deploy.yml`.

### Docker permission denied

Tambahkan user ke group Docker:

```bash
sudo usermod -aG docker $USER
newgrp docker
```

Jika runner service sudah berjalan sebelum user masuk group Docker, restart runner:

```bash
sudo ./svc.sh stop
sudo ./svc.sh start
```

### Health check gagal

Cek container:

```bash
docker compose -f infra/docker/docker-compose.yml ps
```

Cek log backend:

```bash
docker compose -f infra/docker/docker-compose.yml logs --tail=100 backend
```

Cek log nginx:

```bash
docker compose -f infra/docker/docker-compose.yml logs --tail=100 nginx
```

Pastikan `.env.production` punya:

```env
NGINX_HTTP_PORT=8080
```

atau jika memakai port lain, pastikan Cloudflare Tunnel mengarah ke port yang sama.

### Domain Cloudflare tidak bisa dibuka

Cek Cloudflare Tunnel:

```bash
sudo systemctl status cloudflared
```

Cek log Cloudflare Tunnel:

```bash
journalctl -u cloudflared -n 100 --no-pager
```

Pastikan public hostname mengarah ke:

```text
http://localhost:8080
```

### File upload atau PDF tidak tersimpan

Pastikan folder storage ada:

```bash
ls -la storage
```

Workflow deploy sudah membuat folder:

```text
storage/receipts
storage/voice_notes
storage/reports
storage/temp
```

### Session WhatsApp hilang

Jangan menghapus Docker volume:

```bash
docker compose -f infra/docker/docker-compose.yml down -v
```

Session WAHA disimpan di volume Docker `waha_sessions`.

## 12. Catatan Security

- Jangan expose PostgreSQL, Redis, backend direct, frontend direct, atau WAHA dashboard ke internet jika tidak perlu.
- Cloudflare Tunnel cukup diarahkan ke Nginx app di `localhost:8080`.
- Simpan semua secret di GitHub Secrets atau file `.env` lokal server.
- Jangan commit `.env.production`.
- Gunakan repository private untuk self-hosted runner.
- Batasi siapa yang boleh push ke branch `main`.
- Aktifkan branch protection jika project mulai dipakai serius.

## Checklist Selesai

- [ ] Docker dan Docker Compose sudah terinstall di Ubuntu.
- [ ] Cloudflare Tunnel aktif sebagai service.
- [ ] Public hostname Cloudflare mengarah ke `localhost:8080`.
- [ ] GitHub self-hosted runner online.
- [ ] Runner punya label `sakoo-prod`.
- [ ] Secret `PRODUCTION_ENV` sudah dibuat.
- [ ] Secret `GOOGLE_CREDENTIALS_JSON` dibuat jika OCR/STT Google dipakai.
- [ ] Workflow `.github/workflows/deploy.yml` sudah masuk branch `main`.
- [ ] `https://app.domainkamu.com/health` mengembalikan status OK.
