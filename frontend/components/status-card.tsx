type StatusTone = "green" | "blue" | "amber";

type StatusCardProps = {
  label: string;
  value: string;
  tone: StatusTone;
};

const toneClassName: Record<StatusTone, string> = {
  green: "border-emerald-200 bg-emerald-50 text-emerald-700",
  blue: "border-sky-200 bg-sky-50 text-sky-700",
  amber: "border-amber-200 bg-amber-50 text-amber-700",
};

export function StatusCard({ label, value, tone }: StatusCardProps) {
  return (
    <article className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-sm font-medium text-slate-500">{label}</p>
      <div className="mt-4 flex items-center justify-between gap-3">
        <p className="text-lg font-semibold text-slate-950">{value}</p>
        <span
          className={`rounded-md border px-2 py-1 text-xs font-semibold ${toneClassName[tone]}`}
        >
          Ready
        </span>
      </div>
    </article>
  );
}
