type KpiCardProps = {
  label: string;
  value: string;
  unit?: string;
  hint?: string;
};

export function KpiCard({ label, value, unit, hint }: KpiCardProps) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <p className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
        {label}
      </p>
      <p className="mt-2 text-2xl font-semibold text-zinc-900 dark:text-zinc-50">
        {value}
        {unit ? (
          <span className="ml-1 text-sm font-normal text-zinc-500 dark:text-zinc-400">
            {unit}
          </span>
        ) : null}
      </p>
      {hint ? (
        <p className="mt-1 text-xs text-zinc-400 dark:text-zinc-500">{hint}</p>
      ) : null}
    </div>
  );
}
