export type FieldStatusLevel = "normal" | "attention" | "warning" | "critical" | "not_tracked";

export type FieldStatusItem = {
  label: string;
  level: FieldStatusLevel;
  hint?: string;
};

const LEVEL_STYLES: Record<FieldStatusLevel, string> = {
  normal: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  attention: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  warning: "bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300",
  critical: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
  not_tracked: "bg-zinc-200 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400",
};

const LEVEL_ICON: Record<FieldStatusLevel, string> = {
  normal: "\u{1F7E2}",
  attention: "\u{1F7E1}",
  warning: "\u{1F7E0}",
  critical: "\u{1F534}",
  not_tracked: "⚪",
};

const LEVEL_LABEL: Record<FieldStatusLevel, string> = {
  normal: "Normal",
  attention: "Attention",
  warning: "Warning",
  critical: "Critical",
  not_tracked: "Not tracked",
};

export function FieldStatusRow({ items }: { items: FieldStatusItem[] }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
        Field Status
      </h3>
      <div className="mt-3 flex flex-wrap gap-3">
        {items.map((item) => (
          <div
            key={item.label}
            title={item.hint}
            className={`flex items-center gap-2 rounded-full px-3 py-1.5 text-sm font-medium ${LEVEL_STYLES[item.level]}`}
          >
            <span aria-hidden="true">{LEVEL_ICON[item.level]}</span>
            <span>{item.label}</span>
            <span className="text-xs font-normal opacity-80">{LEVEL_LABEL[item.level]}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
