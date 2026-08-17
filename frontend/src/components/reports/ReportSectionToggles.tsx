import { formatLabel } from "@/lib/format";

type ReportSectionTogglesProps = {
  available: string[];
  selected: string[];
  onChange: (selected: string[]) => void;
  disabled?: boolean;
};

/** Every report type has a fixed superset of possible sections; this toggles which of them get
 * computed and included — an unchecked section costs zero backend queries (see
 * services/report_calculations.py's `_wants()`), not just a display filter. */
export function ReportSectionToggles({ available, selected, onChange, disabled }: ReportSectionTogglesProps) {
  function toggle(key: string) {
    onChange(selected.includes(key) ? selected.filter((s) => s !== key) : [...selected, key]);
  }

  return (
    <div className="flex flex-wrap gap-3">
      {available.map((key) => (
        <label key={key} className="flex items-center gap-2 rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700">
          <input type="checkbox" disabled={disabled} checked={selected.includes(key)} onChange={() => toggle(key)} />
          {formatLabel(key)}
        </label>
      ))}
    </div>
  );
}
