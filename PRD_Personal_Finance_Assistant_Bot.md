---
title: "Product Requirement Document (PRD)"
subtitle: "Personal Finance Assistant Bot Berbasis WhatsApp, Telegram, dan Web Dashboard"
author: "Draft PRD"
date: "2026-06-26"
geometry: margin=1in
fontsize: 11pt
lang: id-ID
---

# Product Requirement Document (PRD)

## 1. Ringkasan Produk

Personal Finance Assistant Bot adalah sistem asisten keuangan pribadi yang membantu pengguna mencatat, mengelola, menganalisis, dan mengekspor laporan keuangan harian melalui WhatsApp, Telegram, dan Web Dashboard.

Sistem menggunakan WAHA sebagai WhatsApp Gateway, Telegram Bot API untuk Telegram, Google Vision API untuk OCR struk, dan Google Speech-to-Text untuk voice note. Backend menggunakan FastAPI dengan PostgreSQL sebagai database utama.

Contoh input pengguna:

```text
beli makan 20 ribu
bayar bensin 30rb kemarin
gaji masuk 2 juta
export laporan bulan ini
```

Output sistem berupa data transaksi terstruktur, laporan keuangan, grafik dashboard, dan file PDF laporan.

---

## 2. Tujuan Produk

1. Memudahkan pengguna mencatat pemasukan dan pengeluaran melalui WhatsApp, Telegram, dan Dashboard.
2. Mengubah pesan natural menjadi data transaksi terstruktur.
3. Membaca foto struk menggunakan Google Vision API.
4. Memproses voice note menggunakan Google Speech-to-Text.
5. Menampilkan laporan keuangan harian, mingguan, bulanan, dan custom period.
6. Menyediakan export laporan PDF dari bot dan dashboard.
7. Menjaga sistem tetap ringan agar dapat berjalan pada VPS 2 CPU dan 4 GB RAM.

---

## 3. Target Pengguna

| Target | Keterangan |
|---|---|
| Mahasiswa | Mencatat pengeluaran harian seperti makan, kos, transportasi, pulsa, dan kebutuhan kuliah. |
| Pekerja muda | Memantau pemasukan, pengeluaran, dan tagihan rutin. |
| Freelancer | Mencatat pemasukan proyek dan pengeluaran operasional. |
| Pengguna individu | Membutuhkan pencatatan keuangan cepat melalui chat. |

---

## 4. Masalah dan Solusi

| Masalah | Solusi Produk |
|---|---|
| Pengguna malas membuka aplikasi keuangan | Transaksi dicatat langsung lewat WhatsApp/Telegram. |
| Input manual terlalu lama | Parser membaca nominal, kategori, tanggal, dan tipe transaksi. |
| Struk belanja sulit direkap | Google Vision API membaca teks struk. |
| Pengguna lebih mudah bicara daripada mengetik | Voice note diproses dengan Google Speech-to-Text. |
| Laporan manual sulit dibuat | Sistem menyediakan export PDF otomatis. |
| Pengguna sulit melihat pola pengeluaran | Dashboard menampilkan grafik dan ringkasan keuangan. |

---

## 5. Scope MVP

Fitur yang masuk MVP:

1. Register dan login user.
2. Account linking WhatsApp, Telegram, dan Dashboard.
3. Input transaksi melalui WhatsApp menggunakan WAHA.
4. Input transaksi melalui Telegram Bot.
5. Input transaksi manual melalui Dashboard.
6. Parser transaksi berbasis Regex, Rule-Based, dan ML sederhana.
7. OCR struk menggunakan Google Vision API.
8. Voice note menggunakan Google Speech-to-Text.
9. CRUD transaksi pemasukan dan pengeluaran.
10. Kategori transaksi otomatis.
11. Laporan harian, mingguan, bulanan, dan custom period.
12. Export laporan PDF dari WhatsApp, Telegram, dan Dashboard.
13. Dashboard ringkasan keuangan dan grafik kategori.
14. Riwayat transaksi dan filter berdasarkan tanggal/kategori.
15. Background job untuk OCR, STT, dan PDF.

---

## 6. Batasan MVP dan Fitur yang Ditunda

Agar sistem aman dijalankan pada VPS 2 CPU dan 4 GB RAM, fitur berikut ditunda:

| Ditunda | Alasan |
|---|---|
| Whisper lokal | Berat untuk VPS 4 GB RAM. Voice note memakai Google Speech-to-Text lebih dulu. |
| Monitoring berat | Prometheus, Grafana, dan Loki ditunda agar resource tetap ringan. |
| Admin dashboard kompleks | Fokus MVP pada user dashboard dan fitur utama. |
| Multi-user skala besar | MVP ditujukan untuk production kecil dan penggunaan terbatas. |
| LLM lokal | Model lokal membutuhkan RAM/CPU besar. Parser MVP memakai rule-based dan ML ringan. |

Batasan operasional MVP:

1. Satu session WAHA untuk satu nomor WhatsApp bot.
2. Celery worker dibatasi 1 worker dengan concurrency 1-2.
3. Upload foto struk dibatasi maksimal 2-5 MB.
4. Voice note dibatasi maksimal 30 detik per pesan.
5. OCR dan export PDF diberi rate limit per user.
6. File disimpan di local storage dulu, dengan struktur yang siap dipindah ke MinIO/S3.

---

## 7. Tech Stack Final

| Komponen | Tech Stack | Catatan |
|---|---|---|
| Backend | FastAPI Python | Backend utama dan API service. |
| Database | PostgreSQL | Menyimpan user, transaksi, laporan, log, dan metadata file. |
| ORM | SQLAlchemy / SQLModel | Mapping database. |
| Migration | Alembic | Versi perubahan database. |
| Queue/Cache | Redis | Broker Celery dan cache ringan. |
| Background Job | Celery | OCR, STT, PDF, dan reminder. |
| WhatsApp Gateway | WAHA | Menerima dan mengirim pesan WhatsApp. |
| Telegram | Telegram Bot API | Bot alternatif dan MVP channel. |
| OCR | Google Vision API | Membaca teks dari foto struk. |
| Voice Note | Google Speech-to-Text | Transkripsi voice note. |
| Parser | Regex + Rule-Based + scikit-learn | Parser transaksi dan klasifikasi kategori. |
| PDF Export | WeasyPrint | Generate PDF dari HTML template. |
| Dashboard | Next.js | Web dashboard user. |
| Styling | Tailwind CSS | UI dashboard. |
| Chart | Recharts | Grafik pemasukan/pengeluaran. |
| Reverse Proxy | Nginx | Routing, HTTPS, dan webhook endpoint. |
| Deployment | Docker Compose | Menjalankan semua service di VPS. |
| SSL | Certbot | HTTPS untuk dashboard dan webhook. |
| Testing | Pytest + Postman | Unit test dan API test. |
| Logging MVP | Python logging + database logs | Monitoring ringan tanpa stack berat. |

---

## 8. Arsitektur Sistem

```text
WhatsApp User / Telegram User / Web Dashboard
                    |
                    v
              Nginx / HTTPS
                    |
                    v
             FastAPI Backend
                    |
   +----------------+----------------+----------------+
   |                |                |                |
   v                v                v                v
Auth Service   Bot Service     Parser Service   Report Service
   |                |                |                |
   +----------------+----------------+----------------+
                    |
                    v
              PostgreSQL
                    |
                    v
             Redis + Celery
                    |
      +-------------+-------------+-------------+
      |             |             |             |
      v             v             v             v
   OCR Job       STT Job       PDF Job      Reminder Job
      |             |             |
      v             v             v
Google Vision   Google STT    WeasyPrint
```

---

## 9. Modul Utama

### 9.1 Auth Service

Fungsi:

1. Register user.
2. Login user.
3. JWT authentication.
4. Password hashing dengan bcrypt atau Argon2.
5. Role user dan admin sederhana.

Acceptance criteria:

- User dapat register dan login.
- Password tidak disimpan dalam bentuk plain text.
- User hanya dapat mengakses data miliknya sendiri.

### 9.2 Account Linking Service

Fungsi:

1. Menghubungkan akun Dashboard dengan WhatsApp dan Telegram.
2. Menggunakan kode linking dari dashboard.

Flow:

```text
User login dashboard
    -> generate kode linking
    -> user kirim "hubungkan KODE" ke WhatsApp/Telegram
    -> backend validasi kode
    -> platform terhubung ke user
```

Acceptance criteria:

- User yang belum terhubung diminta mengirim kode linking.
- Kode linking memiliki masa berlaku.
- Satu user dapat terhubung ke WhatsApp dan Telegram.

### 9.3 Bot Service

Fungsi:

1. Menerima pesan dari WAHA dan Telegram.
2. Membedakan jenis pesan: text, image, audio, command.
3. Mengirim balasan teks.
4. Mengirim file PDF.
5. Meneruskan input ke parser, OCR, STT, atau report service.

Acceptance criteria:

- Bot dapat menerima pesan teks.
- Bot dapat menerima foto struk.
- Bot dapat menerima voice note.
- Bot dapat mengirim PDF laporan.

### 9.4 Parser Service

Fungsi:

1. Mendeteksi intent.
2. Mengambil nominal transaksi.
3. Mendeteksi tanggal transaksi.
4. Menentukan tipe transaksi: income atau expense.
5. Menentukan kategori transaksi.
6. Menghasilkan output JSON.

Metode:

| Kebutuhan | Metode |
|---|---|
| Nominal | Regex |
| Tanggal | Rule-Based |
| Tipe transaksi | Keyword rules |
| Intent | Rule-Based + ML ringan |
| Kategori | TF-IDF + Logistic Regression |
| Validasi | Backend rules |

Contoh output:

```json
{
  "intent": "add_transaction",
  "type": "expense",
  "amount": 18000,
  "category": "Makanan",
  "description": "beli ayam geprek",
  "transaction_date": "2026-06-26",
  "source": "whatsapp_text",
  "confidence": 0.91,
  "need_confirmation": false
}
```

Acceptance criteria:

- Parser dapat membaca nominal seperti 20 ribu, 20rb, 20k, Rp20.000, dan 2 juta.
- Parser dapat membedakan pemasukan dan pengeluaran.
- Parser dapat menentukan kategori dasar.
- Jika confidence rendah, bot meminta konfirmasi.

### 9.5 OCR Service - Google Vision API

Fungsi:

1. Menerima foto struk dari WhatsApp, Telegram, atau Dashboard.
2. Mengirim gambar ke Google Vision API.
3. Mengambil raw text hasil OCR.
4. Memproses raw text dengan receipt parser.
5. Menampilkan hasil OCR ke user untuk konfirmasi.

Data yang diambil dari struk:

| Data | Status MVP |
|---|---|
| Total belanja | Wajib |
| Nama merchant | Opsional |
| Tanggal transaksi | Opsional |
| Item detail | Ditunda |
| Metode pembayaran | Opsional |

Acceptance criteria:

- Sistem dapat membaca teks dari gambar struk.
- Sistem dapat mengambil total belanja jika struk jelas.
- Sistem meminta konfirmasi sebelum transaksi disimpan.
- Jika OCR gagal, user diarahkan input manual.

### 9.6 STT Service - Google Speech-to-Text

Fungsi:

1. Menerima voice note dari WhatsApp atau Telegram.
2. Mengunduh file audio dari WAHA/Telegram.
3. Mengirim audio ke Google Speech-to-Text.
4. Mengubah hasil transkrip menjadi input parser.
5. Menampilkan hasil transaksi ke user untuk konfirmasi.

Batasan:

- Durasi voice note maksimal 30 detik.
- Fitur Whisper lokal ditunda.
- Voice note yang tidak jelas akan diminta ulang.

Acceptance criteria:

- Sistem dapat menerima audio.
- Audio berhasil ditranskrip menjadi teks.
- Hasil transkrip dapat diproses parser.
- Jika gagal, bot memberi pesan error yang jelas.

### 9.7 Transaction Service

Fungsi:

1. CRUD transaksi.
2. Simpan pemasukan dan pengeluaran.
3. Edit dan hapus transaksi.
4. Filter transaksi berdasarkan tanggal, kategori, dan sumber.

Acceptance criteria:

- User dapat menambah, melihat, mengedit, dan menghapus transaksi.
- Transaksi dari bot dan dashboard tersimpan dengan source yang jelas.

### 9.8 Report Service dan PDF Export

Fungsi:

1. Membuat laporan harian, mingguan, bulanan, dan custom period.
2. Menghitung total pemasukan, pengeluaran, dan saldo bersih.
3. Menghasilkan file PDF menggunakan WeasyPrint.
4. Mengirim PDF ke WhatsApp/Telegram atau menyediakan download dari dashboard.

Isi PDF:

1. Judul laporan.
2. Nama user.
3. Periode laporan.
4. Tanggal export.
5. Total pemasukan.
6. Total pengeluaran.
7. Saldo bersih.
8. Ringkasan kategori.
9. Daftar transaksi.
10. Insight sederhana.

Acceptance criteria:

- PDF dapat dibuat dari Dashboard.
- PDF dapat dikirim melalui WhatsApp via WAHA.
- PDF dapat dikirim melalui Telegram.
- Data PDF sesuai dengan database.

---

## 10. Bot Command

| Command | Fungsi |
|---|---|
| beli makan 20 ribu | Menambah pengeluaran. |
| gaji masuk 2 juta | Menambah pemasukan. |
| laporan hari ini | Melihat laporan harian. |
| laporan bulan ini | Melihat laporan bulanan. |
| export laporan bulan ini | Membuat dan mengirim PDF. |
| riwayat transaksi | Menampilkan transaksi terbaru. |
| hapus transaksi terakhir | Menghapus transaksi terakhir. |
| bantuan | Menampilkan panduan bot. |

Contoh response transaksi berhasil:

```text
Transaksi berhasil dicatat.
Jenis: Pengeluaran
Nominal: Rp20.000
Kategori: Makanan
Catatan: beli makan
Tanggal: Hari ini
```

Contoh response OCR:

```text
Saya membaca struk berikut:
Toko: Indomaret
Total: Rp58.500
Tanggal: 26 Juni 2026

Apakah ingin disimpan?
Balas: Ya / Edit
```

---

## 11. Database Requirement

### 11.1 users

```text
id
name
email
password_hash
phone_number
created_at
updated_at
```

### 11.2 user_platform_accounts

```text
id
user_id
platform
platform_user_id
phone_number
chat_id
linked_at
is_active
```

### 11.3 account_linking_codes

```text
id
user_id
code
expired_at
used_at
created_at
```

### 11.4 transactions

```text
id
user_id
type
amount
category_id
description
transaction_date
source
created_at
updated_at
```

Nilai `source`:

```text
whatsapp_text
telegram_text
dashboard_manual
receipt_ocr
voice_note
```

### 11.5 categories

```text
id
name
type
created_at
```

Kategori default:

```text
Makanan
Transportasi
Tagihan
Belanja
Hiburan
Kesehatan
Pendidikan
Gaji
Tabungan
Lainnya
```

### 11.6 media_files

```text
id
user_id
file_type
original_filename
stored_path
mime_type
size
source
created_at
```

### 11.7 receipts

```text
id
user_id
media_file_id
ocr_text
merchant_name
receipt_date
total_amount
confidence
status
transaction_id
created_at
```

### 11.8 voice_notes

```text
id
user_id
media_file_id
transcript_text
stt_provider
transaction_id
status
created_at
```

### 11.9 reports

```text
id
user_id
period_start
period_end
report_type
file_id
generated_from
status
created_at
```

### 11.10 jobs

```text
id
user_id
job_type
status
result_id
error_message
created_at
completed_at
```

### 11.11 bot_logs

```text
id
user_id
platform
message_type
raw_message
parsed_result
status
error_message
created_at
```

---

## 12. API Requirement

### Auth API

```text
POST /auth/register
POST /auth/login
GET /auth/me
```

### Account Linking API

```text
POST /linking/generate
POST /linking/verify
GET /linking/platforms
```

### Transaction API

```text
POST /transactions
GET /transactions
GET /transactions/{id}
PUT /transactions/{id}
DELETE /transactions/{id}
```

### Webhook API

```text
POST /webhook/waha
POST /webhook/telegram
```

### OCR API

```text
POST /ocr/receipt
POST /ocr/confirm
```

### STT API

```text
POST /stt/transcribe
POST /stt/confirm
```

### Report API

```text
GET /reports/summary
GET /reports/category
GET /reports/pdf
POST /reports/pdf/generate
GET /files/{file_id}/download
```

### Health API

```text
GET /health
GET /health/db
GET /health/redis
GET /health/waha
```

---

## 13. Non-Functional Requirements

### 13.1 Security

1. Dashboard menggunakan JWT authentication.
2. Password menggunakan bcrypt atau Argon2.
3. File struk, audio, dan PDF hanya dapat diakses melalui backend.
4. Webhook WAHA dan Telegram memakai secret token.
5. API key disimpan di environment variable.
6. Data keuangan tidak boleh dicetak mentah ke log.
7. User hanya dapat mengakses data miliknya sendiri.

### 13.2 Performance

| Proses | Target |
|---|---|
| Response bot teks | Maksimal 3 detik. |
| Dashboard load laporan | Maksimal 5 detik. |
| OCR struk | Background job. |
| STT voice note | Background job. |
| Export PDF | Maksimal 10 detik untuk laporan standar. |

### 13.3 Reliability

1. Jika WAHA logout, sistem mencatat error dan health check gagal.
2. Jika OCR gagal, user diminta input manual.
3. Jika STT gagal, user diminta mengulang voice note.
4. Jika PDF gagal dibuat, user mendapat pesan error.
5. Jika database gagal, bot tidak mengirim konfirmasi palsu.

### 13.4 Resource Constraint VPS

Target server: VPS 2 CPU dan 4 GB RAM.

Konfigurasi awal:

| Service | Konfigurasi |
|---|---|
| FastAPI | 1-2 Uvicorn worker. |
| Celery | 1 worker, concurrency 1-2. |
| PostgreSQL | Lokal dengan konfigurasi ringan. |
| Redis | Lokal. |
| WAHA | 1 session. |
| Next.js | Production build. |
| Monitoring | Health endpoint dan logs sederhana. |

---

## 14. Deployment Plan

Service Docker Compose:

```text
backend
frontend
postgres
redis
celery_worker
celery_beat
waha
nginx
```

Environment variable utama:

```text
DATABASE_URL=
REDIS_URL=
JWT_SECRET=
TELEGRAM_BOT_TOKEN=
WAHA_BASE_URL=
WAHA_API_KEY=
GOOGLE_APPLICATION_CREDENTIALS=
STORAGE_PATH=
APP_BASE_URL=
```

Deployment target:

1. VPS Ubuntu.
2. Docker Compose.
3. Nginx reverse proxy.
4. Certbot SSL.
5. Backup PostgreSQL menggunakan pg_dump terjadwal.

---

## 15. Testing Requirement

### 15.1 Parser Test

| Input | Expected |
|---|---|
| beli makan 20 ribu | expense, Rp20.000, Makanan |
| bayar bensin 30rb kemarin | expense, Rp30.000, Transportasi, tanggal kemarin |
| gaji masuk 2 juta | income, Rp2.000.000, Gaji |
| export laporan bulan ini | intent export_pdf |
| laporan minggu ini | intent get_report |

### 15.2 WAHA Test

| Test | Expected |
|---|---|
| Kirim teks WhatsApp | Backend menerima webhook. |
| Kirim foto struk | Backend menerima media. |
| Kirim voice note | Backend menerima audio. |
| Kirim PDF | User menerima file PDF. |
| WAHA logout | Health check gagal. |

### 15.3 Google Vision Test

| Test | Expected |
|---|---|
| Struk jelas | Total transaksi terbaca. |
| Struk buram | User diminta input manual. |
| Gambar bukan struk | Sistem menolak atau meminta input manual. |
| Banyak nominal | Sistem memilih total akhir dan meminta konfirmasi. |

### 15.4 Google Speech-to-Text Test

| Voice Note | Expected |
|---|---|
| beli makan dua puluh ribu | Transkrip terbaca dan parser menghasilkan Rp20.000. |
| bayar bensin tiga puluh ribu | Transaksi transportasi Rp30.000. |
| audio tidak jelas | Bot meminta user mengulang. |
| durasi lebih dari 30 detik | Bot menolak dan meminta voice note lebih singkat. |

### 15.5 PDF Test

| Test | Expected |
|---|---|
| Export laporan harian | PDF berhasil dibuat. |
| Export laporan bulanan | PDF berhasil dibuat. |
| Data kosong | PDF tetap dibuat dengan keterangan tidak ada transaksi. |
| Export dari WhatsApp | PDF terkirim via WAHA. |
| Download dashboard | PDF terunduh. |

---

## 16. Success Metrics

| Metrik | Target |
|---|---|
| Parser membaca nominal dengan benar | Minimal 90% pada test case umum. |
| Parser membaca kategori dengan benar | Minimal 80% pada kategori utama. |
| Response bot teks | Maksimal 3 detik. |
| Google Vision membaca total struk jelas | Minimal 70%. |
| Google Speech-to-Text berhasil untuk audio jelas | Minimal 80%. |
| Export PDF berhasil | Minimal 95% request berhasil. |
| WAHA menerima pesan WhatsApp | Minimal 95% pada pengujian internal. |
| Dashboard laporan sesuai database | 100% sesuai data transaksi. |

---

## 17. Risiko dan Mitigasi

| Risiko | Dampak | Mitigasi |
|---|---|---|
| WAHA session logout | WhatsApp bot tidak aktif | Health check dan notifikasi admin. |
| Nomor WhatsApp terkena pembatasan | Bot tidak bisa digunakan | Batasi spam, gunakan nomor khusus, hindari broadcast. |
| Google Vision gagal membaca struk | Data OCR salah | Wajib konfirmasi user sebelum simpan. |
| Google Speech-to-Text gagal | Voice note tidak tercatat | Minta user mengulang atau input teks. |
| Parser salah membaca nominal | Transaksi salah | Confidence score dan konfirmasi jika ragu. |
| VPS kekurangan RAM | Service lambat/crash | Batasi worker, aktifkan swap, tunda fitur berat. |
| PDF gagal dibuat | User tidak menerima laporan | Retry job dan error handling. |
| Data keuangan bocor | Risiko privasi | JWT, proteksi file, validasi user_id. |

---

## 18. Timeline MVP

| Minggu | Fokus | Output |
|---|---|---|
| 1 | Setup project | FastAPI, PostgreSQL, Docker, struktur project. |
| 2 | Auth dan transaksi | Register, login, CRUD transaksi, kategori. |
| 3 | Parser dan Telegram | Parser teks, Telegram Bot, simpan transaksi via chat. |
| 4 | WAHA WhatsApp | Setup WAHA, webhook WhatsApp, reply bot. |
| 5 | Dashboard | Next.js dashboard, grafik, riwayat transaksi. |
| 6 | Google Vision OCR | Upload struk, OCR, receipt parser, konfirmasi user. |
| 7 | Google Speech-to-Text dan PDF | Voice note, STT, export PDF dashboard dan bot. |
| 8 | Testing dan deployment | Bug fixing, deploy VPS, dokumentasi, demo. |

---

## 19. Phase Lanjutan Setelah MVP

Fitur lanjutan:

1. Budgeting per kategori.
2. Reminder pembayaran rutin.
3. Export Excel.
4. Admin dashboard sederhana.
5. MinIO/S3 untuk file storage.
6. Monitoring Prometheus dan Grafana.
7. WhatsApp Cloud API resmi untuk production publik.
8. LLM fallback untuk input yang sangat ambigu.
9. Whisper lokal jika VPS/server sudah lebih kuat.
10. Multi-user skala besar setelah optimasi arsitektur.

---

## 20. Kesimpulan

Personal Finance Assistant Bot adalah sistem pencatatan keuangan pribadi berbasis WhatsApp, Telegram, dan Web Dashboard. Sistem menggunakan WAHA untuk WhatsApp, Google Vision API untuk OCR struk, Google Speech-to-Text untuk voice note, FastAPI sebagai backend, PostgreSQL sebagai database, dan WeasyPrint untuk export laporan PDF.

MVP dibatasi agar dapat berjalan pada VPS 2 CPU dan 4 GB RAM. Fitur berat seperti Whisper lokal, monitoring berat, admin dashboard kompleks, multi-user skala besar, dan LLM lokal ditunda. Fokus awal adalah input transaksi via chat, OCR struk, voice note berbasis cloud, dashboard laporan, dan export PDF.
