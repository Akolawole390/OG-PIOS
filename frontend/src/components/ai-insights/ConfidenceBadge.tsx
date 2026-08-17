"use client";

import { formatLabel } from "@/lib/format";

const CONFIDENCE_STYLES: Record<string, string> = {
  high: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  medium: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  low: "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
};

export function ConfidenceBadge({ confidence }: { confidence: string }) {
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
        CONFIDENCE_STYLES[confidence] ?? CONFIDENCE_STYLES.low
      }`}
    >
      {formatLabel(confidence)} confidence
    </span>
  );
}
