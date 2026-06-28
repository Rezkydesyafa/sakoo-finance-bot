# WAHA WhatsApp Gateway

Dokumen ini menjelaskan setup WAHA untuk gateway WhatsApp sesuai PRD Personal Finance Assistant Bot.

## Environment

Isi variabel berikut di `.env` sebelum menjalankan Docker Compose:

```env
WAHA_BASE_URL=http://localhost:3002
WAHA_API_KEY=<long-random-api-key>
WAHA_DASHBOARD_USERNAME=<dashboard-username>
WAHA_DASHBOARD_PASSWORD=<long-random-dashboard-password>
WAHA_SESSION_NAME=default
WAHA_TIMEOUT_SECONDS=10
WAHA_WEBHOOK_URL=http://backend:8000/webhook/waha
WAHA_WEBHOOK_EVENTS=message
WAHA_WEBHOOK_HMAC_KEY=<optional-long-random-webhook-secret>
```

Di dalam Docker network, backend memakai `WAHA_BASE_URL=http://waha:3000` melalui override di `infra/docker/docker-compose.yml`. Nilai `http://localhost:3002` di `.env` dipakai untuk akses dari host lokal.

`WAHA_WEBHOOK_HMAC_KEY` bersifat opsional untuk local development. Jika diisi, backend akan memverifikasi header `X-Webhook-Hmac-Algorithm: sha512` dan `X-Webhook-Hmac` dari WAHA sebelum menyimpan event.

## Menjalankan WAHA

Untuk menjalankan bot WhatsApp end-to-end, jalankan backend, database, Redis, dan WAHA:

```bash
docker compose -f infra/docker/docker-compose.yml up -d --build backend postgres redis waha
```

Jalankan migration:

```bash
docker compose -f infra/docker/docker-compose.yml exec backend alembic upgrade head
```

Jika hanya ingin menjalankan service WAHA:

```bash
docker compose -f infra/docker/docker-compose.yml up -d waha
```

WAHA tersedia di:

```text
http://localhost:3002
```

Dashboard WAHA tersedia di:

```text
http://localhost:3002/dashboard
```

Login ke dashboard memakai `WAHA_DASHBOARD_USERNAME` dan `WAHA_DASHBOARD_PASSWORD`, lalu connect ke server memakai `WAHA_API_KEY`.

Cek log WAHA dan backend:

```bash
docker compose -f infra/docker/docker-compose.yml logs -f waha backend
```

## Session WhatsApp dan Scan QR

1. Buka `http://localhost:3002/dashboard`.
2. Masuk dengan credential dashboard dari `.env`.
3. Connect memakai API key dari `.env`.
4. Start session `default` atau nilai dari `WAHA_SESSION_NAME`.
5. Tunggu status session menjadi `SCAN_QR_CODE` atau `SCAN_QR`.
6. Klik ikon kamera/QR pada dashboard.
7. Di WhatsApp mobile, buka Linked Devices, lalu scan QR.
8. Pastikan status session berubah menjadi `WORKING`.

Jika dashboard menampilkan pesan untuk reload QR, stop session lalu start lagi.

## Cek Status Session

```bash
curl -H "X-Api-Key: $WAHA_API_KEY" \
  http://localhost:3002/api/sessions/default
```

Status yang diharapkan setelah scan QR berhasil:

```json
{"status":"WORKING"}
```

## Health Check Backend

Backend menyediakan endpoint health check WAHA supaya status session bisa dipantau tanpa Grafana:

```bash
curl http://localhost:8000/health/waha
```

Response sehat:

```json
{
  "status": "ok",
  "healthy": true,
  "session": "default",
  "session_status": "WORKING",
  "warning": null,
  "checked_at": "2026-06-27T12:00:00+00:00",
  "raw": {
    "status": "WORKING"
  }
}
```

Jika session logout, stopped, butuh scan QR, atau WAHA API tidak bisa diakses, endpoint mengembalikan HTTP `503`:

```json
{
  "detail": {
    "status": "error",
    "healthy": false,
    "session": "default",
    "session_status": "STOPPED",
    "warning": "WAHA session is not active. session=default, status=STOPPED",
    "checked_at": "2026-06-27T12:00:00+00:00",
    "raw": {
      "status": "STOPPED"
    }
  }
}
```

Setiap warning health check dicatat ke `bot_logs` dengan `platform=system`, `message_type=waha_health`, dan `status=waha_unhealthy`. Field `warning` pada response bisa dipakai untuk alert sederhana ke admin/dev.

## Webhook Backend

WAHA dikonfigurasi melalui Docker Compose untuk mengirim event `message` ke backend:

```text
http://backend:8000/webhook/waha
```

Variable yang mengatur webhook WAHA:

```env
WAHA_WEBHOOK_URL=http://backend:8000/webhook/waha
WAHA_WEBHOOK_EVENTS=message
WAHA_WEBHOOK_HMAC_KEY=<optional-long-random-webhook-secret>
```

Jika akses melalui Nginx dari luar container, URL publiknya:

```text
http://localhost/webhook/waha
```

Endpoint `POST /webhook/waha` menerima payload WAHA, membaca:

- pesan teks dari `payload.body`, `payload.text`, atau `payload.caption`;
- foto/struk dari `payload.media` dengan MIME type `image/*`;
- voice note/audio dari `payload.media` dengan MIME type `audio/*`;
- identitas WhatsApp dari `payload.from`, `payload.chatId`, `payload.participant`, atau `payload.author`.

Setiap event disimpan ke tabel `bot_logs` dengan `platform=whatsapp`, `message_type`, `raw_message`, dan metadata parsing. Jika nomor sudah tertaut di `user_platform_accounts`, `user_id` ikut dicatat; jika belum tertaut, log tetap disimpan dengan `user_id=null`.

Contoh test manual:

```bash
curl -X POST \
  http://localhost:8000/webhook/waha \
  -H "Content-Type: application/json" \
  -d '{
    "event": "message",
    "session": "default",
    "payload": {
      "from": "6281234567890@c.us",
      "body": "beli makan 20 ribu",
      "hasMedia": false
    }
  }'
```

## Account Linking via WhatsApp

User menghubungkan akun dashboard ke WhatsApp dengan kode linking dari dashboard.

Flow:

1. User login dashboard dan membuat kode linking.
2. User mengirim pesan WhatsApp ke bot:

```text
hubungkan KODE
```

3. Backend memvalidasi kode pada tabel `account_linking_codes`.
4. Jika kode valid, belum digunakan, dan belum expired, backend menyimpan atau memperbarui `user_platform_accounts` dengan:

- `platform=whatsapp`
- `platform_user_id` berisi nomor WhatsApp tanpa suffix `@c.us`
- `phone_number` berisi nomor WhatsApp tanpa suffix `@c.us`
- `chat_id` berisi chat id WAHA lengkap, misalnya `6281234567890@c.us`

5. Backend menandai `account_linking_codes.used_at`.
6. Backend membalas sukses atau gagal melalui WAHA.

Jika nomor belum terhubung dan pesan bukan command `hubungkan KODE`, bot akan membalas instruksi agar user membuat kode linking di dashboard.

Kode invalid, sudah digunakan, atau expired akan ditolak dan dicatat di `bot_logs`.

## Transaksi Teks via WhatsApp

Setelah nomor WhatsApp terhubung ke akun dashboard, user dapat mencatat transaksi dengan pesan teks natural.

Contoh:

```text
beli kopi 18 ribu
bayar bensin 30rb kemarin
gaji masuk 2 juta
```

Backend akan:

1. Menerima event WAHA di `POST /webhook/waha`.
2. Mencari user linked dari `user_platform_accounts`.
3. Memproses nominal, tipe transaksi, tanggal, kategori, dan deskripsi dengan parser regex/rule-based.
4. Menyimpan transaksi dengan `source=whatsapp_text` jika confidence cukup.
5. Membalas ringkasan transaksi melalui WAHA.

Nominal yang didukung untuk MVP:

- `20 ribu`
- `20rb`
- `20k`
- `Rp20.000`
- `2 juta`

Jika parser belum yakin, misalnya nominal tidak terbaca, transaksi tidak disimpan dan bot meminta user mengirim ulang dengan format lebih jelas.

## OCR Foto Struk via WhatsApp

Nomor WhatsApp yang sudah linked dapat mengirim foto struk langsung ke bot. Backend akan:

1. Menerima event image dari WAHA.
2. Mengunduh media dari URL WAHA.
3. Menyimpan file sebagai `media_files` dengan `file_type=receipt` dan `source=whatsapp_receipt`.
4. Membuat row `jobs` dengan `job_type=receipt_ocr`.
5. Menjalankan Google Vision OCR dan parser struk.
6. Membalas hasil OCR ke WhatsApp dan meminta konfirmasi.

Contoh balasan bot:

```text
Foto struk sudah diproses OCR. Merchant: TOKO SAKOO. Tanggal: 2026-06-27. Total: Rp20.000. Confidence: 100%. Ketik YA untuk menyimpan transaksi, atau edit total 20000 untuk koreksi.
```

Konfirmasi:

```text
YA
```

Koreksi total:

```text
edit total 21000
```

Setelah user membalas `YA`, backend menyimpan transaksi dengan `source=receipt_ocr`, `type=expense`, kategori default `Lainnya`, dan menghubungkan `receipts.transaction_id` ke transaksi tersebut.

## Checklist End-to-End WhatsApp Bot

1. Isi `.env`:

```env
POSTGRES_USER=sakoo
POSTGRES_PASSWORD=<password>
POSTGRES_DB=sakoo_finance
JWT_SECRET=<long-random-jwt-secret>
WAHA_API_KEY=<long-random-api-key>
WAHA_DASHBOARD_USERNAME=admin
WAHA_DASHBOARD_PASSWORD=<long-random-password>
WAHA_SESSION_NAME=default
WAHA_WEBHOOK_URL=http://backend:8000/webhook/waha
WAHA_WEBHOOK_EVENTS=message
```

2. Jalankan service:

```bash
docker compose -f infra/docker/docker-compose.yml up -d --build backend postgres redis waha
```

3. Jalankan migration:

```bash
docker compose -f infra/docker/docker-compose.yml exec backend alembic upgrade head
```

4. Buka dashboard WAHA:

```text
http://localhost:3002/dashboard
```

5. Start session `default`.
6. Scan QR dari WhatsApp mobile.
7. Pastikan status session `WORKING`.
8. Hubungkan nomor WhatsApp ke akun dashboard:

```text
hubungkan KODE
```

9. Kirim transaksi:

```text
beli makan 20 ribu
```

10. Cek transaksi tersimpan di database dengan `source=whatsapp_text`.

## Restart dan Recovery Session

Restart container WAHA tanpa menghapus session:

```bash
docker compose -f infra/docker/docker-compose.yml restart waha
```

Restart session WAHA melalui API dengan stop lalu start:

```bash
curl -X POST \
  -H "X-Api-Key: $WAHA_API_KEY" \
  http://localhost:3002/api/sessions/default/stop

curl -X POST \
  -H "X-Api-Key: $WAHA_API_KEY" \
  http://localhost:3002/api/sessions/default/start
```

Jika session gagal karena perangkat logout atau disconnect:

1. Coba restart session.
2. Jika tetap gagal, logout session dari dashboard/API.
3. Start session ulang.
4. Scan QR ulang.

Session disimpan pada named volume Docker `waha_sessions`, sehingga restart container tidak menghapus login WhatsApp. Menghapus volume `waha_sessions` akan menghapus data session dan membutuhkan scan QR ulang.

## Test Kirim Pesan

Ganti `6281234567890` dengan nomor tujuan tanpa tanda `+`.

```bash
curl -X POST \
  http://localhost:3002/api/sendText \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $WAHA_API_KEY" \
  -d '{
    "chatId": "6281234567890@c.us",
    "text": "Tes WAHA dari Sakoo Finance Bot",
    "session": "default"
}'
```

## Test Kirim File PDF

`send_file` pada backend memakai endpoint WAHA `POST /api/sendFile`. File PDF yang disimpan di local storage dapat diunduh user melalui endpoint protected `GET /api/media/{media_id}/download` memakai JWT. Untuk mengirim PDF ke WAHA dari backend tanpa membuka file sebagai URL publik, gunakan payload data base64 atau helper `WahaClient.send_file(file_data=...)`.

Contoh via data base64:

```bash
curl -X POST \
  http://localhost:3002/api/sendFile \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $WAHA_API_KEY" \
  -d '{
    "chatId": "6281234567890@c.us",
    "session": "default",
    "caption": "Laporan keuangan",
    "file": {
      "data": "<base64-pdf-content>",
      "mimetype": "application/pdf",
      "filename": "laporan.pdf"
    }
  }'
```

Untuk production, batasi akses port WAHA di firewall/reverse proxy dan simpan semua credential hanya di `.env` atau secret manager.
