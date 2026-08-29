type SubScore = { label: string; score: number | null };

export function OperationsScoreCard({ subScores }: { subScores: SubScore[] }) {
  const known = subScores.filter((s): s is { label: string; score: number } => s.score !== null);
  const overall = known.length > 0 ? Math.round(known.reduce((sum, s) => sum + s.score, 0) / known.length) : null;

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex items-center gap-1.5">
        <p className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
          Operations Score
        </p>
        <span className="rounded border border-zinc-300 px-1 text-[10px] font-medium uppercase tracking-wide text-zinc-400 dark:border-zinc-700 dark:text-zinc-500">
          Estimated
        </span>
      </div>
      <p className="mt-2 text-3xl font-semibold text-zinc-900 dark:text-zinc-50">
        {overall !== null ? overall : "—"}
        <span className="ml-1 text-sm font-normal text-zinc-500 dark:text-zinc-400">/ 100</span>
      </p>
      <ul className="mt-3 flex flex-col gap-1">
        {subScores.map((s) => (
          <li key={s.label} className="flex items-center justify-between text-xs text-zinc-500 dark:text-zinc-400">
            <span>{s.label}</span>
            <span className="font-medium text-zinc-700 dark:text-zinc-300">{s.score !== null ? s.score : "—"}</span>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-[11px] text-zinc-400 dark:text-zinc-500">
        Estimated composite score derived from current KPI data, not a certified metric.
      </p>
    </div>
  );
}
