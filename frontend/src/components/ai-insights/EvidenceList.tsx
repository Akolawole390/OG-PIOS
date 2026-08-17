"use client";

import type { InsightEvidence } from "@/lib/api";

const EVIDENCE_GROUPS: { type: InsightEvidence["evidence_type"]; label: string; hint: string; style: string }[] = [
  {
    type: "observed_fact",
    label: "Observed Facts",
    hint: "Directly recorded in OG-PIOS — not calculated or inferred.",
    style: "border-blue-300 bg-blue-50 dark:border-blue-800 dark:bg-blue-950/30",
  },
  {
    type: "calculated_metric",
    label: "Calculated Metrics",
    hint: "Computed deterministically from recorded data.",
    style: "border-purple-300 bg-purple-50 dark:border-purple-800 dark:bg-purple-950/30",
  },
  {
    type: "correlation",
    label: "Correlations",
    hint: "Two or more signals co-occurring — not a claim of cause.",
    style: "border-amber-300 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30",
  },
  {
    type: "possible_contributor",
    label: "Possible Contributors",
    hint: "May be related — requires engineering review, never a confirmed cause.",
    style: "border-orange-300 bg-orange-50 dark:border-orange-800 dark:bg-orange-950/30",
  },
];

export function EvidenceList({ evidence }: { evidence: InsightEvidence[] }) {
  if (evidence.length === 0) {
    return <p className="text-sm text-zinc-500 dark:text-zinc-400">No evidence recorded for this insight.</p>;
  }

  return (
    <div className="flex flex-col gap-4">
      {EVIDENCE_GROUPS.map((group) => {
        const items = evidence.filter((e) => e.evidence_type === group.type);
        if (items.length === 0) return null;
        return (
          <div key={group.type} className={`rounded-lg border p-4 ${group.style}`}>
            <div className="mb-2 flex items-baseline justify-between gap-3">
              <h4 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">{group.label}</h4>
              <span className="text-xs text-zinc-500 dark:text-zinc-400">{group.hint}</span>
            </div>
            <ul className="space-y-1.5 text-sm text-zinc-700 dark:text-zinc-300">
              {items.map((item) => (
                <li key={item.id} className="flex flex-wrap items-baseline gap-x-2">
                  <span>{item.description}</span>
                  {item.value !== null ? (
                    <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400">
                      ({item.value}
                      {item.unit ? ` ${item.unit}` : ""})
                    </span>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}
