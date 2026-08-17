"use client";

import { formatLabel } from "@/lib/format";

const STATUS_STYLES: Record<string, string> = {
  new: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  acknowledged: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  investigating: "bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300",
  resolved: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  dismissed: "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
};

export function AlertStatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
        STATUS_STYLES[status] ?? STATUS_STYLES.new
      }`}
    >
      {formatLabel(status)}
    </span>
  );
}
