"use client";

const DOT_STYLES: Record<"good" | "warning" | "unknown", string> = {
  good: "bg-green-500",
  warning: "bg-amber-500",
  unknown: "bg-zinc-400",
};

/** True for exact-match healthy states like "connected"/"running"/"ok"/"configured" — anything
 * else (including "not configured (using deterministic fallback)", which is a normal, expected
 * app state, not a fault) renders as a neutral "unknown" dot rather than a false-alarm warning. */
const GOOD_VALUES = new Set(["connected", "running", "ok", "configured", "operational"]);

export function StatusCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  const tone: "good" | "warning" | "unknown" = GOOD_VALUES.has(value.toLowerCase())
    ? "good"
    : value.toLowerCase().includes("unavailable") || value.toLowerCase().includes("error")
      ? "warning"
      : "unknown";

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <p className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">{label}</p>
      <div className="mt-2 flex items-center gap-2">
        <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${DOT_STYLES[tone]}`} aria-hidden />
        <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">{value}</p>
      </div>
      {hint ? <p className="mt-1 text-xs text-zinc-400 dark:text-zinc-500">{hint}</p> : null}
    </div>
  );
}
