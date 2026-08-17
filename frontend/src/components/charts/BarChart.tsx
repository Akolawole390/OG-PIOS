"use client";

import { useId } from "react";
import {
  Bar,
  BarChart as RechartsBarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export type BarDatum = {
  key: string;
  label: string;
  value: number;
};

type TooltipPayloadEntry = {
  value?: number;
  payload?: BarDatum;
};

function CustomTooltip({
  active,
  payload,
  unit,
}: {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  unit?: string;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const entry = payload[0];
  if (!entry.payload) return null;

  return (
    <div className="rounded-md border border-zinc-200 bg-white px-3 py-2 text-xs shadow-sm dark:border-zinc-700 dark:bg-zinc-900">
      <span className="font-semibold text-zinc-900 dark:text-zinc-50">{entry.value?.toLocaleString()}</span>
      <span className="ml-1 text-zinc-500 dark:text-zinc-400">
        {unit ?? ""} — {entry.payload.label}
      </span>
    </div>
  );
}

type BarChartProps = {
  title: string;
  data: BarDatum[];
  unit?: string;
  highlightKey?: string;
};

/**
 * Nominal-categorical ranking chart (production by well/field/facility, top/lowest wells).
 * All bars share one hue (dataviz rule: swapping a nominal category's order never changes
 * its meaning, so identity is carried by the label, not by per-bar color) — the validated
 * slot-1 blue from the Wells module's line-chart palette, reused here without needing a new
 * multi-color CVD validation pass.
 */
export function BarChart({ title, data, unit, highlightKey }: BarChartProps) {
  const titleId = useId();
  const rowHeight = 32;
  const chartHeight = Math.max(data.length * rowHeight, rowHeight * 2);

  return (
    <div
      role="img"
      aria-labelledby={titleId}
      className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950"
    >
      <h3 id={titleId} className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">
        {title}
      </h3>

      {data.length === 0 ? (
        <p className="mt-6 text-sm text-zinc-500 dark:text-zinc-400">No data available yet.</p>
      ) : (
        <div className="mt-3 w-full" style={{ height: chartHeight }}>
          <ResponsiveContainer width="100%" height="100%">
            <RechartsBarChart
              data={data}
              layout="vertical"
              margin={{ top: 4, right: 32, left: 8, bottom: 4 }}
              barCategoryGap={2}
            >
              <CartesianGrid stroke="var(--chart-grid)" strokeDasharray="0" horizontal={false} />
              <XAxis type="number" hide />
              <YAxis
                type="category"
                dataKey="label"
                tick={{ fill: "var(--chart-text-muted)", fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                width={90}
              />
              <Tooltip cursor={{ fill: "var(--chart-grid)" }} content={<CustomTooltip unit={unit} />} />
              <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={20} isAnimationActive={false}>
                {data.map((entry) => (
                  <Cell
                    key={entry.key}
                    fill={
                      highlightKey && entry.key === highlightKey
                        ? "var(--chart-series-2)"
                        : "var(--chart-series-1)"
                    }
                  />
                ))}
                <LabelList
                  dataKey="value"
                  position="right"
                  style={{ fill: "var(--chart-text-secondary)", fontSize: 11 }}
                  formatter={(value: unknown) => (typeof value === "number" ? value.toLocaleString() : String(value ?? ""))}
                />
              </Bar>
            </RechartsBarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
