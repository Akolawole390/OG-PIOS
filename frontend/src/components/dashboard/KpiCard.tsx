type KpiCardProps = {
  label: string;
  value: string;
  unit?: string;
  hint?: string;
  /** Set for KPIs derived via a formula/conversion factor (e.g. BOE, target variance) rather
   * than a direct sum/count of stored data — renders a small "Calculated" badge so raw and
   * derived figures are visually distinguishable. */
  calculated?: boolean;
};

export function KpiCard({ label, value, unit, hint, calculated }: KpiCardProps) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex items-center gap-1.5">
        <p className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
          {label}
        </p>
        {calculated ? (
          <span className="rounded border border-zinc-300 px-1 text-[10px] font-medium uppercase tracking-wide text-zinc-400 dark:border-zinc-700 dark:text-zinc-500">
            Calculated
          </span>
        ) : null}
      </div>
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
