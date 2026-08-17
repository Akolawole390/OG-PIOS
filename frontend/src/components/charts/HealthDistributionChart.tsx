"use client";

import { useId } from "react";

export type HealthDistributionBucket = {
  band: string;
  count: number;
};

type HealthDistributionChartProps = {
  title: string;
  buckets: HealthDistributionBucket[];
  unscoredCount?: number;
};

// Fixed, ordinal, reserved-meaning scale — never themed, never cycled, always icon+label
// (never color alone) per the dataviz skill's status rule. Distinct from the categorical
// --chart-series-* tokens used elsewhere (BarChart, TrendChart) for identity encoding.
export const HEALTH_BAND_CONFIG: Record<string, { color: string; icon: string }> = {
  Excellent: { color: "var(--status-excellent)", icon: "★" },
  Good: { color: "var(--status-good)", icon: "✓" },
  Monitor: { color: "var(--status-monitor)", icon: "!" },
  "Maintenance Required": { color: "var(--status-maintenance-required)", icon: "▲" },
  Critical: { color: "var(--status-critical)", icon: "✕" },
};

export const HEALTH_BAND_ORDER = ["Excellent", "Good", "Monitor", "Maintenance Required", "Critical"];

const BAND_CONFIG = HEALTH_BAND_CONFIG;
const BAND_ORDER = HEALTH_BAND_ORDER;

export function HealthDistributionChart({ title, buckets, unscoredCount }: HealthDistributionChartProps) {
  const titleId = useId();
  const countByBand = new Map(buckets.map((b) => [b.band, b.count]));
  const total = buckets.reduce((sum, b) => sum + b.count, 0);

  return (
    <div
      role="img"
      aria-labelledby={titleId}
      className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950"
    >
      <h3 id={titleId} className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">
        {title}
      </h3>

      {total === 0 ? (
        <p className="mt-6 text-sm text-zinc-500 dark:text-zinc-400">No scored equipment yet.</p>
      ) : (
        <div className="mt-4 flex flex-col gap-2.5">
          {BAND_ORDER.map((band) => {
            const count = countByBand.get(band) ?? 0;
            const config = BAND_CONFIG[band];
            const widthPct = total > 0 ? (count / total) * 100 : 0;
            return (
              <div key={band} className="flex items-center gap-3">
                <span
                  className="flex w-6 shrink-0 items-center justify-center text-sm font-bold"
                  style={{ color: config.color }}
                  aria-hidden="true"
                >
                  {config.icon}
                </span>
                <span className="w-40 shrink-0 text-sm text-zinc-700 dark:text-zinc-300">{band}</span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-900">
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${widthPct}%`, backgroundColor: config.color }}
                  />
                </div>
                <span
                  className="w-8 shrink-0 text-right text-sm font-medium text-zinc-900 dark:text-zinc-50"
                  style={{ fontVariantNumeric: "tabular-nums" }}
                >
                  {count}
                </span>
              </div>
            );
          })}
          {unscoredCount !== undefined && unscoredCount > 0 ? (
            <p className="mt-1 text-xs text-zinc-400 dark:text-zinc-500">
              {unscoredCount} item{unscoredCount === 1 ? "" : "s"} not yet scored (insufficient data).
            </p>
          ) : null}
        </div>
      )}
    </div>
  );
}
