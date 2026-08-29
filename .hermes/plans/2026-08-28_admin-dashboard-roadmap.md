# Sakoo Admin Dashboard Roadmap Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Mengembangkan Admin Dashboard Sakoo dari landing page sederhana menjadi pusat operasi yang aman untuk memantau sistem, provider LLM, pengguna, pekerjaan asynchronous, audit, dan deployment.

**Architecture:** Backend menyediakan endpoint admin-only berbasis `ADMIN_EMAILS` dengan response agregat yang tidak membocorkan secret. Frontend tetap memakai query-tab dashboard yang ada, dengan komponen admin terpisah dan lazy fetch per panel. Setiap fase menggunakan TDD, default-deny authorization, pagination, dan audit trail.

**Tech Stack:** FastAPI, SQLAlchemy, PostgreSQL, Celery/Redis, Docker Compose, Next.js/React, TypeScript, GitHub Actions.

---

## Current Context

- Admin status berasal dari backend (`is_admin`) dan allowlist `ADMIN_EMAILS`.
- Admin Dashboard tersedia di `/?tab=admin`.
- LLM Providers tersedia di `/?tab=llm-providers`.
- API key provider dienkripsi Fernet dan tidak pernah dikembalikan mentah.
- Provider database aktif mengoverride env fallback chain.
- Check Connection dan Fetch Models sudah delivered di production; fase berikutnya menyimpan health metrics historis per provider.
- Deployment production memakai self-hosted runner, GHCR, dan Docker Compose project `docker`.

## Product Principles

1. **Default deny:** semua endpoint `/admin/*` wajib `require_admin`.
2. **No secret exposure:** dashboard tidak boleh menampilkan token, API key, password, credential JSON, atau `.env`.
3. **Read-heavy first:** fase awal fokus visibility; aksi destruktif ditambahkan belakangan dengan konfirmasi dan audit.
4. **Operationally useful:** setiap kartu harus menjawab status, dampak, dan tindakan berikutnya.
5. **Pagination and bounded queries:** hindari query semua user/log/job sekaligus.
6. **Auditability:** setiap perubahan konfigurasi admin dicatat dengan actor, action, target, timestamp, dan metadata aman.

---

### Task 1: System Health Summary

**Objective:** Menampilkan status backend, PostgreSQL, Redis, WAHA, Celery, dan provider LLM pada Admin Dashboard.

**Files:**
- Create: `backend/app/modules/admin_dashboard.py`
- Modify: `backend/app/api/v1/router.py`
- Create: `backend/tests/test_admin_dashboard.py`
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/components/tabs/admin-overview-tab.tsx`

**Steps:**
1. Tulis test gagal untuk `GET /api/admin/dashboard/summary` sebagai admin dan 403 sebagai non-admin.
2. Implementasikan response terstruktur: `services`, `llm_providers`, `jobs`, `users`, `generated_at`.
3. Gunakan timeout pendek untuk dependency checks; jangan memblokir keseluruhan response jika satu service gagal.
4. Tambahkan cards hijau/kuning/merah dengan `last_checked` dan pesan singkat.
5. Jalankan `pytest -q backend/tests/test_admin_dashboard.py`, frontend tests, lint, dan build.

**Acceptance:** halaman admin langsung menunjukkan service mana yang sehat/gagal tanpa membuka terminal.

---

### Task 2: LLM Provider Operational Metrics

**Objective:** Menampilkan availability, latency terakhir, model aktif, priority, dan error terakhir per provider.

**Files:**
- Modify: `backend/app/models/llm_provider.py`
- Create: `backend/alembic/versions/<revision>_add_llm_provider_health.py`
- Modify: `backend/app/modules/admin_llm_providers.py`
- Modify: `backend/app/modules/llm/llm_router.py`
- Modify: `frontend/components/tabs/llm-providers-tab.tsx`
- Test: `backend/tests/test_admin_llm_providers.py`

**Steps:**
1. Tulis test gagal untuk penyimpanan `last_checked_at`, `last_latency_ms`, `last_status`, dan error yang disanitasi.
2. Tambahkan migration kolom health tanpa mengubah encrypted key.
3. Simpan hasil check manual dan kegagalan runtime secara bounded.
4. Tampilkan badge health serta waktu check terakhir.
5. Tambahkan filter active/offline/degraded.

**Acceptance:** operator dapat melihat provider bermasalah dan kapan terakhir sukses tanpa membocorkan upstream error yang berisi secret.

---

### Task 3: User Administration (Read-Only First)

**Objective:** Menampilkan daftar user, platform tertaut, tanggal daftar, dan aktivitas terakhir secara aman.

**Files:**
- Create: `backend/app/modules/admin_users.py`
- Modify: `backend/app/api/v1/router.py`
- Create: `backend/tests/test_admin_users.py`
- Create: `frontend/components/tabs/admin-users-tab.tsx`
- Modify: `frontend/components/dashboard-shell.tsx`
- Modify: `frontend/app/(dashboard)/page.tsx`
- Modify: `frontend/lib/api.ts`

**Steps:**
1. Test admin-only paginated endpoint `GET /api/admin/users?limit=&offset=&q=`.
2. Return hanya data aman: id, name, email, platform list, created_at, updated_at.
3. Jangan return password hash, tokens, linking codes, atau private provider config.
4. Tambahkan search email/nama dan pagination.
5. Tambahkan menu `Users` hanya untuk admin.

**Acceptance:** admin dapat mencari user tanpa memperoleh credential atau data finansial user.

---

### Task 4: Jobs and Integration Operations

**Objective:** Memberikan visibility terhadap Celery jobs, OCR/STT/report failures, dan akun platform yang bermasalah.

**Files:**
- Create: `backend/app/modules/admin_jobs.py`
- Create: `backend/tests/test_admin_jobs.py`
- Create: `frontend/components/tabs/admin-jobs-tab.tsx`
- Modify: admin navigation and `frontend/lib/api.ts`

**Steps:**
1. Test endpoint paginated dengan filter status/type/date.
2. Return error message yang disanitasi dan result identifiers, bukan payload rahasia.
3. Tambahkan detail drawer dan tombol retry hanya untuk job idempotent.
4. Catat retry ke audit log.

**Acceptance:** admin dapat mengetahui job gagal dan melakukan retry aman tanpa akses shell.

---

### Task 5: Immutable Admin Audit Log

**Objective:** Mencatat perubahan provider, retry job, perubahan user, dan tindakan admin lain.

**Files:**
- Create: `backend/app/models/admin_audit_log.py`
- Create: `backend/alembic/versions/<revision>_add_admin_audit_logs.py`
- Create: `backend/app/modules/admin_audit.py`
- Create: `backend/tests/test_admin_audit.py`
- Create: `frontend/components/tabs/admin-audit-tab.tsx`

**Steps:**
1. Test log tercipta saat create/update/delete/check provider.
2. Simpan actor user id/email, action, target type/id, status, timestamp, metadata aman.
3. Larang penyimpanan API key, JWT, password, atau raw upstream response.
4. Sediakan endpoint read-only paginated dengan filter actor/action/date.
5. Tambahkan tab Audit Log.

**Acceptance:** semua mutasi admin dapat ditelusuri tanpa secret leakage.

---

### Task 6: Deployment and Runtime Visibility

**Objective:** Menampilkan versi aplikasi dan status deploy terakhir tanpa memberi akses arbitrary shell.

**Files:**
- Modify: `.github/workflows/ci.yml` untuk menyematkan commit SHA sebagai image label/env.
- Modify: `infra/docker/docker-compose.yml` untuk `APP_COMMIT_SHA` bila diperlukan.
- Extend: `backend/app/modules/admin_dashboard.py`
- Modify: `frontend/components/tabs/admin-overview-tab.tsx`

**Steps:**
1. Tambahkan test response version/commit.
2. Expose hanya commit SHA, build time, app version, container startup time.
3. Tampilkan link ke commit/Actions run jika tersedia.
4. Jangan expose Docker socket atau command execution endpoint.

**Acceptance:** admin mengetahui kode versi mana yang sedang berjalan dan kapan terakhir deploy.

---

### Task 7: Controlled Admin Actions

**Objective:** Menambahkan aksi berisiko secara bertahap dengan guard yang kuat.

**Initial Scope:**
- Enable/disable LLM provider.
- Retry job idempotent.
- Revoke platform linking session bila model mendukung.

**Explicitly Out of Scope:**
- Arbitrary SQL.
- Arbitrary shell/Docker commands.
- View/edit raw production env.
- Display secret values.
- Delete production volumes.

**Steps:**
1. Tulis test authorization, CSRF assumptions, idempotency, audit, dan confirmation token.
2. Tambahkan reason wajib untuk tindakan berisiko.
3. Terapkan rate limit admin mutation.
4. Return explicit outcome dan audit id.

---

## Recommended Navigation

```text
Admin Dashboard
├── Overview
├── LLM Providers
├── Users
├── Jobs & Integrations
├── Audit Log
└── Runtime & Deployments
```

## Suggested Admin Overview Layout

1. **Top summary:** app health, deploy SHA, uptime, active users.
2. **Service health row:** API, DB, Redis, Celery, WAHA.
3. **LLM providers:** healthy/degraded/offline counts and primary provider.
4. **Operational queue:** pending/failed jobs in last 24h.
5. **Recent admin activity:** five latest audit records.
6. **Quick links:** provider management, users, jobs, audit.

## Testing and Validation

Backend:
```bash
python -m pytest -q
ruff check app tests
mypy app
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

Frontend:
```bash
npm test
npm run lint
npm run build
```

Security review:
- Verify every `/admin/*` endpoint returns 401 without token and 403 for non-admin.
- Search responses and logs for API key/token/password leakage.
- Verify pagination limits and bounded dependency timeouts.
- Verify no endpoint can access arbitrary URL except intentionally configured provider URLs.

Production verification:
- CI green.
- Deploy green.
- `/health` HTTP 200.
- Admin overview loads with verified admin account.
- Non-admin cannot load admin API data.
- Container restart counts remain stable.

## Risks and Tradeoffs

- Health probes can add upstream load; cache results briefly and use manual refresh/rate limit.
- Admin email allowlist is simple but not granular; migrate to DB-backed roles before adding high-risk actions.
- Provider base URLs intentionally support private networks for local gateways; admin access and audit remain mandatory.
- Runtime Docker visibility should use build metadata, not mounting Docker socket into the backend.
- User administration should remain read-only until audit log and granular roles exist.

## Recommended Delivery Order

1. System Health Summary.
2. Provider Operational Metrics.
3. Audit Log.
4. User Read-Only Administration.
5. Jobs & Integrations.
6. Runtime/Deployment Visibility.
7. Controlled actions after security review.
