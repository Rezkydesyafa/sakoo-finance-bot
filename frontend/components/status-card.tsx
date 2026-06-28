type StatusTone = "green" | "blue" | "amber" | "slate";

type StatusCardProps = {
  label: string;
  value: string;
  tone: StatusTone;
  detail?: string;
};

const toneClassName: Record<StatusTone, string> = {
  green: "bg-emerald-500",
  blue: "bg-sky-500",
  amber: "bg-amber-500",
  slate: "bg-slate-400",
};

export function StatusCard({ label, value, tone, detail }: StatusCardProps) {
  return (
    <article className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-sm font-medium text-slate-500">{label}</p>
      <div className="mt-4 flex items-center gap-3">
        <span className={`h-2.5 w-2.5 rounded-full ${toneClassName[tone]}`} />
        <p className="text-base font-semibold text-slate-950">{value}</p>
      </div>
      {detail ? <p className="mt-3 text-sm text-slate-500">{detail}</p> : null}
    </article>
  );
}
