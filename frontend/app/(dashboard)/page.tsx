import { MetricCard } from "@/components/metric-card";
import { StatusCard } from "@/components/status-card";
import { API_BASE_URL } from "@/lib/api";

const metricItems = [
  {
    label: "Saldo bulan ini",
    value: "Rp0",
    helper: "Menunggu transaksi pertama",
  },
  {
    label: "Pemasukan",
    value: "Rp0",
    helper: "Belum ada pemasukan",
  },
  {
    label: "Pengeluaran",
    value: "Rp0",
    helper: "Belum ada pengeluaran",
  },
  {
    label: "Perlu konfirmasi",
    value: "0",
    helper: "OCR dan chat tertunda",
  },
];

const statusItems = [
  {
    label: "Backend API",
    value: "Ready",
    tone: "green" as const,
    detail: "/health dan /api aktif",
  },
  {
    label: "WhatsApp Gateway",
    value: "Standby",
    tone: "blue" as const,
    detail: "WAHA session dipantau lewat health check",
  },
  {
    label: "Queue",
    value: "Configured",
    tone: "amber" as const,
    detail: "Redis dan Celery untuk OCR async",
  },
];

export default function Home() {
  return (
    <div className="space-y-6">
      <section className="flex flex-col justify-between gap-3 border-b border-slate-200 pb-6 sm:flex-row sm:items-end">
        <div>
          <p className="text-sm font-semibold uppercase text-emerald-700">
            Overview
          </p>
          <h1 className="mt-2 text-3xl font-semibold text-slate-950">
            Ringkasan keuangan
          </h1>
        </div>
        <p className="max-w-md text-sm text-slate-500 sm:text-right">
          Basis API: {API_BASE_URL}
        </p>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {metricItems.map((item) => (
          <MetricCard
            key={item.label}
            label={item.label}
            value={item.value}
            helper={item.helper}
          />
        ))}
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(320px,0.8fr)]">
        <article className="rounded-lg border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-200 px-5 py-4">
            <h2 className="text-base font-semibold text-slate-950">
              Aktivitas terbaru
            </h2>
          </div>
          <div className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-3 px-5 py-5 text-sm">
            <p className="font-medium text-slate-700">Transaksi manual</p>
            <p className="text-right font-semibold text-slate-950">0</p>
            <p className="font-medium text-slate-700">Pesan WhatsApp</p>
            <p className="text-right font-semibold text-slate-950">0</p>
            <p className="font-medium text-slate-700">Pesan Telegram</p>
            <p className="text-right font-semibold text-slate-950">0</p>
            <p className="font-medium text-slate-700">OCR struk</p>
            <p className="text-right font-semibold text-slate-950">0</p>
          </div>
        </article>

        <div className="grid gap-4">
          {statusItems.map((item) => (
            <StatusCard
              key={item.label}
              label={item.label}
              value={item.value}
              tone={item.tone}
              detail={item.detail}
            />
          ))}
        </div>
      </section>
    </div>
  );
}
