"use client";

import { useId } from "react";
import { Bar, BarChart as RechartsBarChart, Cell, LabelList, ResponsiveContainer, XAxis } from "recharts";
import type { ComparisonRow } from "@/lib/api";
import { formatCurrency } from "@/lib/format";

const DIRECTION_CLASS: Record<ComparisonRow["direction"], string> = {
  positive: "text-emerald-600 dark:text-emerald-400",
  negative: "text-red-600 dark:text-red-400",
  neutral: "text-zinc-500 dark:text-zinc-400",
};

const DIRECTION_ICON: Record<ComparisonRow["direction"], string> = {
  positive: "▲",
  negative: "▼",
  neutral: "•",
};

function formatValue(value: number, currency: string | null): string {
  if (currency) return formatCurrency(value, currency);
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function ComparisonTile({ row }: { row: ComparisonRow }) {
  const titleId = useId();
  const data = [
    { label: "Baseline", value: row.baseline },
    { label: "Scenario", value: row.scenario },
  ];

  return (
    <div
      role="img"
      aria-labelledby={titleId}
      className="rounded-lg border border-zinc-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-950"
    >
      <h4 id={titleId} className="truncate text-xs font-semibold text-zinc-900 dark:text-zinc-50">
        {row.metric}
      </h4>
      <div className="mt-1 h-28 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <RechartsBarChart data={data} margin={{ top: 16, right: 4, left: 4, bottom: 0 }} barCategoryGap={24}>
            <XAxis
              dataKey="label"
              tick={{ fill: "var(--chart-text-muted)", fontSize: 10 }}
              axisLine={{ stroke: "var(--chart-axis)" }}
              tickLine={false}
            />
            <Bar dataKey="value" radius={[3, 3, 0, 0]} isAnimationActive={false}>
              {data.map((entry, index) => (
                <Cell key={entry.label} fill={index === 0 ? "var(--chart-series-1)" : "var(--chart-series-2)"} />
              ))}
              <LabelList
                dataKey="value"
                position="top"
                style={{ fill: "var(--chart-text-secondary)", fontSize: 10 }}
                formatter={(value: unknown) => (typeof value === "number" ? formatValue(value, row.currency) : "")}
              />
            </Bar>
          </RechartsBarChart>
        </ResponsiveContainer>
      </div>
      <p className={`text-center text-xs font-medium ${DIRECTION_CLASS[row.direction]}`}>
        {DIRECTION_ICON[row.direction]}{" "}
        {row.pct_change === null ? "No change" : `${row.pct_change > 0 ? "+" : ""}${row.pct_change.toFixed(1)}%`}
      </p>
    </div>
  );
}

/** Small-multiples grid — one paired Baseline/Scenario bar chart per comparison metric, reusing
 * the exact same `ComparisonRow[]` the ComparisonTable renders (never a second data path), so
 * this stays correct automatically if the backend ever adds another comparison metric. Color
 * encodes Baseline/Scenario identity only (fixed roles, one shared legend below); the good/bad
 * judgment is a separate text annotation, never a bar recolor — keeps the two encodings from
 * conflicting. Complements ComparisonTable, never replaces it — the table stays the exact-number
 * source of truth. */
export function ScenarioComparisonCharts({ rows }: { rows: ComparisonRow[] }) {
  if (rows.length === 0) {
    return <p className="text-sm text-zinc-500 dark:text-zinc-400">No comparison data available.</p>;
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-4 text-xs text-zinc-500 dark:text-zinc-400">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: "var(--chart-series-1)" }} />
          Baseline
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: "var(--chart-series-2)" }} />
          Scenario
        </span>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {rows.map((row) => (
          <ComparisonTile key={`${row.metric}-${row.currency ?? ""}`} row={row} />
        ))}
      </div>
    </div>
  );
}
