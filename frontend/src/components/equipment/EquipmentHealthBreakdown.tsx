"use client";

import { HEALTH_BAND_CONFIG } from "@/components/charts/HealthDistributionChart";
import type { EquipmentHealth } from "@/lib/api";
import { formatLabel } from "@/lib/format";

type EquipmentHealthBreakdownProps = {
  health: EquipmentHealth | null;
};

export function EquipmentHealthBreakdown({ health }: EquipmentHealthBreakdownProps) {
  if (!health) {
    return (
      <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Health Score</h3>
        <p className="mt-3 text-sm text-zinc-500 dark:text-zinc-400">Loading…</p>
      </div>
    );
  }

  const config = HEALTH_BAND_CONFIG[health.band] ?? { color: "var(--status-monitor)", icon: "?" };

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Health Score</h3>
        <span className="text-xs text-zinc-400 dark:text-zinc-500">
          As of {new Date(health.computed_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}
        </span>
      </div>

      <div className="mt-3 flex items-center gap-3">
        <span className="text-3xl font-semibold text-zinc-900 dark:text-zinc-50">{health.score.toFixed(0)}</span>
        <span
          className="flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium"
          style={{ color: config.color, backgroundColor: `color-mix(in srgb, ${config.color} 15%, transparent)` }}
        >
          <span aria-hidden="true">{config.icon}</span>
          {health.band}
        </span>
      </div>

      {health.factors.length > 0 ? (
        <ul className="mt-4 space-y-2 text-sm">
          {health.factors.map((factor) => (
            <li
              key={factor.factor}
              className="flex items-start justify-between gap-3 border-b border-zinc-100 pb-2 last:border-0 dark:border-zinc-900"
            >
              <div>
                <p className="font-medium text-zinc-900 dark:text-zinc-50">{formatLabel(factor.factor)}</p>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">{factor.detail}</p>
              </div>
              <span className="shrink-0 text-red-600 dark:text-red-400">-{factor.deduction.toFixed(1)}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-4 text-sm text-zinc-500 dark:text-zinc-400">
          No deductions — no contributing factors detected in available data.
        </p>
      )}

      <p className="mt-4 text-xs text-zinc-400 dark:text-zinc-500">{health.disclaimer_text}</p>
    </div>
  );
}
