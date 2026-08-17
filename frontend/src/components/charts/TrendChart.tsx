"use client";

import { useId, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export type TrendSeries = {
  key: string;
  label: string;
  color: string;
  unit?: string;
};

type ChartRow = Record<string, number | string | null>;

type TooltipPayloadEntry = {
  dataKey?: string | number;
  value?: number | string;
};

function CustomTooltip({
  active,
  payload,
  label,
  series,
}: {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: string | number;
  series: TrendSeries[];
}) {
  if (!active || !payload || payload.length === 0) return null;

  return (
    <div className="rounded-md border border-zinc-200 bg-white px-3 py-2 text-xs shadow-sm dark:border-zinc-700 dark:bg-zinc-900">
      <p className="mb-1.5 font-medium text-zinc-500 dark:text-zinc-400">{label}</p>
      <div className="space-y-1">
        {series.map((s) => {
          const entry = payload.find((p) => p.dataKey === s.key);
          if (entry === undefined || entry.value === undefined || entry.value === null) {
            return null;
          }
          return (
            <div key={s.key} className="flex items-center gap-2">
              <span className="inline-block h-0.5 w-3 shrink-0" style={{ backgroundColor: s.color }} />
              <span className="font-semibold text-zinc-900 dark:text-zinc-50">{entry.value}</span>
              <span className="text-zinc-500 dark:text-zinc-400">
                {s.label}
                {s.unit ? ` (${s.unit})` : ""}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

type TrendChartProps = {
  title: string;
  data: ChartRow[];
  xKey: string;
  series: TrendSeries[];
  showTableToggle?: boolean;
};

export function TrendChart({ title, data, xKey, series, showTableToggle }: TrendChartProps) {
  const [showTable, setShowTable] = useState(false);
  const titleId = useId();

  return (
    <div
      role="img"
      aria-labelledby={titleId}
      className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950"
    >
      <div className="flex items-center justify-between">
        <h3 id={titleId} className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">
          {title}
        </h3>
        {showTableToggle ? (
          <button
            type="button"
            onClick={() => setShowTable((prev) => !prev)}
            className="text-xs font-medium text-zinc-500 underline-offset-2 hover:text-zinc-900 hover:underline dark:text-zinc-400 dark:hover:text-zinc-50"
          >
            {showTable ? "View chart" : "View as table"}
          </button>
        ) : null}
      </div>

      {data.length === 0 ? (
        <p className="mt-6 text-sm text-zinc-500 dark:text-zinc-400">No data available yet.</p>
      ) : showTable ? (
        <div className="mt-3 max-h-72 overflow-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-zinc-200 text-zinc-500 dark:border-zinc-800 dark:text-zinc-400">
                <th className="py-1.5 pr-4 font-medium">Date</th>
                {series.map((s) => (
                  <th key={s.key} className="py-1.5 pr-4 font-medium">
                    {s.label}
                    {s.unit ? ` (${s.unit})` : ""}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody style={{ fontVariantNumeric: "tabular-nums" }}>
              {data.map((row, index) => (
                <tr key={index} className="border-b border-zinc-100 dark:border-zinc-900">
                  <td className="py-1.5 pr-4 text-zinc-700 dark:text-zinc-300">{row[xKey]}</td>
                  {series.map((s) => (
                    <td key={s.key} className="py-1.5 pr-4 text-zinc-900 dark:text-zinc-50">
                      {row[s.key] ?? "—"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="mt-3 h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="var(--chart-grid)" strokeDasharray="0" vertical={false} />
              <XAxis
                dataKey={xKey}
                tick={{ fill: "var(--chart-text-muted)", fontSize: 11 }}
                axisLine={{ stroke: "var(--chart-axis)" }}
                tickLine={false}
                minTickGap={24}
                tickFormatter={(value: string) => (typeof value === "string" ? value.slice(5) : value)}
              />
              <YAxis
                tick={{ fill: "var(--chart-text-muted)", fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                width={48}
              />
              <Tooltip
                cursor={{ stroke: "var(--chart-axis)", strokeWidth: 1 }}
                content={<CustomTooltip series={series} />}
              />
              {series.length > 1 ? (
                <Legend
                  verticalAlign="top"
                  height={28}
                  iconType="plainline"
                  wrapperStyle={{ fontSize: 12, color: "var(--chart-text-secondary)" }}
                />
              ) : null}
              {series.map((s) => (
                <Line
                  key={s.key}
                  type="monotone"
                  dataKey={s.key}
                  name={s.label}
                  stroke={s.color}
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4, stroke: "var(--chart-surface)", strokeWidth: 2 }}
                  connectNulls
                  isAnimationActive={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
