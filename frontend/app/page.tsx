import { StatusCard } from "@/components/status-card";

const statusItems = [
  {
    label: "Backend API",
    value: "/health",
    tone: "green" as const,
  },
  {
    label: "WhatsApp Gateway",
    value: "WAHA",
    tone: "blue" as const,
  },
  {
    label: "Queue",
    value: "Redis + Celery",
    tone: "amber" as const,
  },
];

export default function Home() {
  return (
    <main className="min-h-screen">
      <div className="mx-auto flex min-h-screen w-full max-w-6xl flex-col px-6 py-8">
        <header className="flex items-center justify-between border-b border-slate-200 pb-5">
          <div>
            <p className="text-sm font-medium uppercase text-slate-500">
              Personal Finance Assistant
            </p>
            <h1 className="mt-2 text-3xl font-semibold text-slate-950">
              Sakoo Finance Bot Dashboard
            </h1>
          </div>
          <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-700">
            MVP Setup
          </div>
        </header>

        <section className="grid flex-1 content-start gap-4 py-8 sm:grid-cols-3">
          {statusItems.map((item) => (
            <StatusCard
              key={item.label}
              label={item.label}
              value={item.value}
              tone={item.tone}
            />
          ))}
        </section>
      </div>
    </main>
  );
}
