# Telegram Bot Integration

Dokumen ini menjelaskan cara membuat bot Telegram, menghubungkannya ke backend Sakoo Finance Bot, dan menguji flow transaksi teks.

## Ringkasan Integrasi

Flow Telegram pada backend:

```text
Telegram User
  -> Telegram Bot API webhook
  -> POST /webhook/telegram
  -> validasi X-Telegram-Bot-Api-Secret-Token
  -> cek account linking Telegram
  -> parser parse_message(text, source="telegram_text")
  -> simpan transaksi jika confidence cukup
  -> balas user via sendMessage
```

Voice note memakai flow yang sama setelah akun linked, tetapi media diunduh lebih dulu dari Telegram Bot API, disimpan sebagai `media_files.file_type=audio`, lalu diproses worker `voice_stt` dengan Google Speech-to-Text.

Endpoint backend:

```text
POST /webhook/telegram
```

Data transaksi yang disimpan dari Telegram memakai:

```text
source=telegram_text
```

## Membuat Bot Telegram

1. Buka Telegram dan cari akun resmi `@BotFather`.
2. Kirim command:

```text
/newbot
```

3. Isi nama bot, misalnya:

```text
Sakoo Finance Bot
```

4. Isi username bot. Username harus unik dan berakhir dengan `bot`, misalnya:

```text
sakoo_finance_dev_bot
```

5. BotFather akan memberi token seperti:

```text
1234567890:AAExampleTelegramBotToken
```

6. Simpan token itu ke `.env`, jangan commit token asli.

Opsional, set command list di BotFather dengan `/setcommands`:

```text
start - Mulai bot
bantuan - Lihat panduan bot
```

Command transaksi seperti `beli makan 20 ribu`, `laporan bulan ini`, dan `export laporan bulan ini` diproses sebagai teks biasa oleh parser.

## Environment

Isi variable berikut di `.env`:

```env
TELEGRAM_BOT_TOKEN=1234567890:AAExampleTelegramBotToken
TELEGRAM_BASE_URL=https://api.telegram.org
TELEGRAM_TIMEOUT_SECONDS=10
TELEGRAM_WEBHOOK_URL=https://your-public-domain.com/webhook/telegram
TELEGRAM_WEBHOOK_SECRET=<long-random-secret>
GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/google-service-account.json
STT_LANGUAGE_CODE=id-ID
STT_MAX_DURATION_SECONDS=30
```

`TELEGRAM_WEBHOOK_SECRET` dipakai untuk validasi header Telegram:

```text
X-Telegram-Bot-Api-Secret-Token
```

Jika `TELEGRAM_WEBHOOK_SECRET` kosong, backend tidak memvalidasi secret header. Untuk production, isi nilai ini.

Buat secret lokal:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

PowerShell:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Menjalankan Backend

Jalankan service dengan Docker Compose:

```bash
docker compose -f infra/docker/docker-compose.yml up -d --build backend postgres redis
```

Backend container menjalankan migration otomatis sebelum API start.

Cek health:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/db
```

## Public URL untuk Webhook

Telegram Bot API membutuhkan webhook HTTPS yang bisa diakses dari internet.

Untuk production, gunakan domain HTTPS milik server, misalnya:

```text
https://api.example.com/webhook/telegram
```

Untuk development lokal, gunakan tunnel seperti ngrok atau Cloudflare Tunnel, lalu arahkan ke backend/Nginx lokal.

Contoh jika tunnel publik mengarah ke Nginx lokal port `80`:

```env
TELEGRAM_WEBHOOK_URL=https://your-tunnel-url.ngrok-free.app/webhook/telegram
```

Contoh jika tunnel publik langsung mengarah ke backend port `8000`:

```env
TELEGRAM_WEBHOOK_URL=https://your-tunnel-url.ngrok-free.app/webhook/telegram
```

Pastikan path tetap:

```text
/webhook/telegram
```

## Set Webhook Telegram

Set webhook ke backend:

```bash
curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  -d "url=$TELEGRAM_WEBHOOK_URL" \
  -d "secret_token=$TELEGRAM_WEBHOOK_SECRET" \
  -d 'allowed_updates=["message"]'
```

PowerShell:

```powershell
$body = @{
  url = $env:TELEGRAM_WEBHOOK_URL
  secret_token = $env:TELEGRAM_WEBHOOK_SECRET
  allowed_updates = '["message"]'
}
Invoke-RestMethod -Method Post `
  -Uri "https://api.telegram.org/bot$env:TELEGRAM_BOT_TOKEN/setWebhook" `
  -Body $body
```

Cek webhook:

```bash
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getWebhookInfo"
```

Hapus webhook jika ingin reset:

```bash
curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/deleteWebhook"
```

## Account Linking Telegram

Sebelum transaksi bisa disimpan, akun Telegram harus terhubung ke user dashboard.

Flow:

1. User register/login via API lalu membuat kode linking:

```bash
curl -X POST http://localhost:8000/api/auth/linking-codes \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

Response berisi `command`, misalnya `hubungkan ABC123`.

2. User mengirim pesan ke bot Telegram:

```text
hubungkan KODE
```

3. Backend memvalidasi kode.
4. Jika valid, backend menyimpan atau memperbarui `user_platform_accounts`:

```text
platform=telegram
platform_user_id=<telegram_user_id>
chat_id=<telegram_chat_id>
is_active=true
```

5. Backend membalas:

```text
Akun Telegram berhasil terhubung ke akun dashboard.
```

Jika user belum linked dan mengirim pesan biasa, bot akan membalas instruksi untuk mengirim `hubungkan KODE`.

## Flow Transaksi Telegram

Setelah akun linked, user bisa mengirim:

```text
beli makan 20 ribu
bayar bensin 30rb kemarin
gaji masuk 2 juta
```

Backend akan:

1. Menerima update Telegram di `POST /webhook/telegram`.
2. Validasi secret webhook.
3. Parse pesan teks.
4. Cari user linked dari `user_platform_accounts`.
5. Panggil parser final:

```python
parse_message(text, source="telegram_text")
```

6. Simpan transaksi jika `need_confirmation=false`.
7. Balas ringkasan transaksi via Telegram `sendMessage`.

Jika nominal tidak terbaca, misalnya:

```text
beli makan
```

Bot tidak menyimpan transaksi dan membalas agar user mengirim ulang dengan format lebih jelas.

## Flow Voice Note Telegram

Setelah akun linked, user dapat mengirim voice note maksimal 30 detik. Backend akan:

1. Menerima update Telegram dengan field `voice` atau `audio`.
2. Menolak durasi di atas `STT_MAX_DURATION_SECONDS`.
3. Mengunduh file dengan `getFile` dan endpoint file Telegram.
4. Menyimpan file sebagai `media_files` dengan `file_type=audio` dan `source=telegram_voice`.
5. Membuat job `voice_stt` status `queued`.
6. Worker memanggil Google Speech-to-Text, menyimpan transcript ke `voice_notes.transcript_text`, lalu menjalankan parser dengan `source=voice_note`.
7. Bot membalas hasil transkripsi atau pesan error yang jelas.

Jika Google STT gagal atau audio tidak jelas, job ditandai `failed`/`manual_input_required` dan user diminta mengirim ulang voice note yang lebih jelas.

## Flow Export PDF Telegram

Setelah akun linked, user dapat meminta laporan PDF dengan pesan:

```text
export laporan bulan ini
```

Backend akan:

1. Menerima update teks di `POST /webhook/telegram`.
2. Mendeteksi intent `export_pdf` dan periode laporan.
3. Membuat job `report_pdf` status `queued`.
4. Worker membuat PDF laporan dengan WeasyPrint, menyimpan file ke `media_files`, dan mencatat metadata laporan di `reports`.
5. Worker mengirim dokumen PDF via Telegram Bot API `sendDocument`.

Balasan awal:

```text
Permintaan export PDF laporan bulan ini sudah masuk antrean. Bot akan mengirim file PDF setelah selesai dibuat.
```

Jika PDF gagal dibuat, bot membalas:

```text
Maaf, PDF laporan gagal dibuat. Coba lagi beberapa saat lagi atau gunakan periode yang berbeda.
```

## Test Manual Webhook

Test webhook backend tanpa Telegram Bot API:

```bash
curl -X POST http://localhost:8000/webhook/telegram \
  -H "Content-Type: application/json" \
  -H "X-Telegram-Bot-Api-Secret-Token: $TELEGRAM_WEBHOOK_SECRET" \
  -d '{
    "update_id": 1001,
    "message": {
      "message_id": 1,
      "from": {
        "id": 123456,
        "is_bot": false,
        "first_name": "Tester",
        "username": "tester"
      },
      "chat": {
        "id": 123456,
        "type": "private"
      },
      "date": 1760000000,
      "text": "beli makan 20 ribu"
    }
  }'
```

Jika akun Telegram belum linked, response akan menunjukkan `linking_status=unlinked` dan backend mencoba membalas instruksi linking melalui Telegram API.

## Test Kirim Pesan Langsung

Ganti `<chat_id>` dengan chat id Telegram user.

```bash
curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
  -d "chat_id=<chat_id>" \
  -d "text=Tes Sakoo Finance Bot"
```

## Troubleshooting

**Webhook tidak masuk**

- Pastikan `TELEGRAM_WEBHOOK_URL` memakai HTTPS dan bisa diakses publik.
- Cek `getWebhookInfo`.
- Cek log backend:

```bash
docker compose -f infra/docker/docker-compose.yml logs -f backend
```

**Response 401 dari backend**

Pastikan `secret_token` saat `setWebhook` sama dengan `TELEGRAM_WEBHOOK_SECRET` di `.env`.

**Bot tidak membalas**

- Pastikan `TELEGRAM_BOT_TOKEN` benar.
- Pastikan backend dapat akses internet ke `https://api.telegram.org`.
- Cek log backend untuk error `telegram_request_failed` atau `telegram_api_error`.

**Transaksi tidak tersimpan**

- Pastikan akun Telegram sudah linked.
- Pastikan kategori default sudah ada.
- Jika bot meminta konfirmasi, parser belum yakin. Kirim ulang dengan nominal jelas, contoh:

```text
beli makan 20 ribu
```

## Catatan Security

- Jangan commit `TELEGRAM_BOT_TOKEN`.
- Isi `TELEGRAM_WEBHOOK_SECRET` untuk production.
- Batasi endpoint production dengan HTTPS valid.
- Simpan token dan secret di `.env` atau secret manager.
