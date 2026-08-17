"use client";

import type { ImportRowAction, ImportRowResult } from "@/lib/api";

const STATUS_STYLES: Record<string, string> = {
  valid: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  warning: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  duplicate: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  invalid: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
};

type ImportPreviewTableProps = {
  rows: ImportRowResult[];
  actions: Record<number, ImportRowAction>;
  onActionChange: (rowNumber: number, action: ImportRowAction) => void;
  onBulkDuplicateAction: (action: "skip" | "overwrite") => void;
};

export function ImportPreviewTable({ rows, actions, onActionChange, onBulkDuplicateAction }: ImportPreviewTableProps) {
  const hasDuplicates = rows.some((r) => r.status === "duplicate");

  return (
    <div className="flex flex-col gap-3">
      {hasDuplicates ? (
        <div className="flex items-center gap-2 text-xs text-zinc-600 dark:text-zinc-400">
          <span>Duplicate rows found — apply to all:</span>
          <button
            type="button"
            onClick={() => onBulkDuplicateAction("skip")}
            className="rounded border border-zinc-300 px-2 py-1 font-medium hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900"
          >
            Skip All
          </button>
          <button
            type="button"
            onClick={() => onBulkDuplicateAction("overwrite")}
            className="rounded border border-zinc-300 px-2 py-1 font-medium hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900"
          >
            Overwrite All
          </button>
        </div>
      ) : null}

      <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-zinc-200 bg-zinc-50 text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
              <th className="px-3 py-2 font-medium">Row</th>
              <th className="px-3 py-2 font-medium">Status</th>
              <th className="px-3 py-2 font-medium">Well</th>
              <th className="px-3 py-2 font-medium">Date</th>
              <th className="px-3 py-2 font-medium">Oil</th>
              <th className="px-3 py-2 font-medium">Messages</th>
              <th className="px-3 py-2 font-medium">Action</th>
            </tr>
          </thead>
          <tbody style={{ fontVariantNumeric: "tabular-nums" }}>
            {rows.map((row) => (
              <tr key={row.row_number} className="border-b border-zinc-100 last:border-0 dark:border-zinc-900">
                <td className="px-3 py-2 text-zinc-500 dark:text-zinc-400">{row.row_number}</td>
                <td className="px-3 py-2">
                  <span className={`inline-block rounded-full px-2 py-0.5 font-medium ${STATUS_STYLES[row.status]}`}>
                    {row.status}
                  </span>
                </td>
                <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">{row.well_id || "—"}</td>
                <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">{row.record_date || "—"}</td>
                <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">
                  {row.parsed.oil_bopd !== undefined && row.parsed.oil_bopd !== null ? String(row.parsed.oil_bopd) : "—"}
                </td>
                <td className="px-3 py-2 text-zinc-500 dark:text-zinc-400">
                  {row.messages.length > 0 ? row.messages.join("; ") : "—"}
                </td>
                <td className="px-3 py-2">
                  {row.status === "invalid" ? (
                    <span className="text-zinc-400">Excluded</span>
                  ) : row.status === "duplicate" ? (
                    <select
                      value={actions[row.row_number] ?? "skip"}
                      onChange={(e) => onActionChange(row.row_number, e.target.value as ImportRowAction)}
                      className="rounded border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900"
                    >
                      <option value="skip">Skip</option>
                      <option value="overwrite">Overwrite</option>
                    </select>
                  ) : (
                    <span className="text-zinc-500 dark:text-zinc-400">Import</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
