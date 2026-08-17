import type { ComparisonRow } from "@/lib/api";
import { formatCurrency } from "@/lib/format";

const DIRECTION_CLASS: Record<ComparisonRow["direction"], string> = {
  positive: "text-emerald-600 dark:text-emerald-400",
  negative: "text-red-600 dark:text-red-400",
  neutral: "text-zinc-500 dark:text-zinc-400",
};

function formatValue(value: number, currency: string | null): string {
  if (currency) return formatCurrency(value, currency);
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function formatSigned(value: number, currency: string | null): string {
  const formatted = formatValue(Math.abs(value), currency);
  if (value > 0) return `+${formatted}`;
  if (value < 0) return `-${formatted}`;
  return formatted;
}

/** Metric | Baseline | Scenario | Difference | % Change — the module spec's own comparison
 * table shape. Color follows `direction` (computed server-side, since "higher is better" isn't
 * uniform across metrics — a cost increase and a revenue increase point opposite ways), never
 * just the sign of the difference. */
export function ComparisonTable({ rows }: { rows: ComparisonRow[] }) {
  if (rows.length === 0) {
    return <p className="text-sm text-zinc-500 dark:text-zinc-400">No comparison data available.</p>;
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-zinc-200 bg-zinc-50 text-xs uppercase tracking-wide text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
            <th className="px-3 py-2 font-medium">Metric</th>
            <th className="px-3 py-2 font-medium">Baseline</th>
            <th className="px-3 py-2 font-medium">Scenario</th>
            <th className="px-3 py-2 font-medium">Difference</th>
            <th className="px-3 py-2 font-medium">% Change</th>
          </tr>
        </thead>
        <tbody style={{ fontVariantNumeric: "tabular-nums" }}>
          {rows.map((row) => (
            <tr key={`${row.metric}-${row.currency ?? ""}`} className="border-b border-zinc-100 last:border-0 dark:border-zinc-900">
              <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">{row.metric}</td>
              <td className="px-3 py-2 text-zinc-900 dark:text-zinc-50">{formatValue(row.baseline, row.currency)}</td>
              <td className="px-3 py-2 text-zinc-900 dark:text-zinc-50">{formatValue(row.scenario, row.currency)}</td>
              <td className={`px-3 py-2 font-medium ${DIRECTION_CLASS[row.direction]}`}>
                {formatSigned(row.difference, row.currency)}
              </td>
              <td className={`px-3 py-2 font-medium ${DIRECTION_CLASS[row.direction]}`}>
                {row.pct_change === null ? "—" : `${row.pct_change > 0 ? "+" : ""}${row.pct_change.toFixed(1)}%`}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
