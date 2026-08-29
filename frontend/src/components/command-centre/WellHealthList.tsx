import Link from "next/link";
import type { WellIssueSummary } from "@/lib/api";

export function WellHealthList({
  downWells,
  zeroProductionWells,
}: {
  downWells: WellIssueSummary[];
  zeroProductionWells: WellIssueSummary[];
}) {
  const items = [...downWells, ...zeroProductionWells].slice(0, 6);

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Wells Requiring Attention</h3>
      {items.length === 0 ? (
        <p className="mt-3 text-sm text-zinc-500 dark:text-zinc-400">No wells flagged as down or at zero production.</p>
      ) : (
        <ul className="mt-3 flex flex-col gap-2.5">
          {items.map((well, index) => (
            <li key={`${well.well_id}-${index}`} className="flex items-start justify-between gap-2 text-sm">
              <Link href={`/wells/${well.well_id}`} className="truncate text-zinc-700 hover:underline dark:text-zinc-300">
                {well.well_code} — {well.well_name}
              </Link>
              <span className="shrink-0 truncate text-xs text-zinc-400 dark:text-zinc-500">{well.detail}</span>
            </li>
          ))}
        </ul>
      )}
      <Link href="/wells" className="mt-3 inline-block text-xs font-medium text-zinc-600 hover:underline dark:text-zinc-400">
        View all wells →
      </Link>
    </div>
  );
}
