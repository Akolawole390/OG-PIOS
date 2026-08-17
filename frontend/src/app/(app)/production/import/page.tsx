"use client";

import { useState, type ChangeEvent } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { ImportPreviewTable } from "@/components/production/ImportPreviewTable";
import {
  confirmProductionImport,
  previewProductionImport,
  type ImportConfirmResponse,
  type ImportConfirmRow,
  type ImportPreviewResponse,
  type ImportRowAction,
} from "@/lib/api";

function num(value: unknown): number | undefined {
  return typeof value === "number" ? value : undefined;
}

function numOrNull(value: unknown): number | null {
  return typeof value === "number" ? value : null;
}

export default function ProductionImportPage() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreviewResponse | null>(null);
  const [actions, setActions] = useState<Record<number, ImportRowAction>>({});
  const [result, setResult] = useState<ImportConfirmResponse | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setFile(event.target.files?.[0] ?? null);
    setPreview(null);
    setResult(null);
    setError(null);
  }

  async function handlePreview() {
    if (!file) return;
    setIsBusy(true);
    setError(null);
    try {
      const response = await previewProductionImport(file);
      setPreview(response);
      const defaultActions: Record<number, ImportRowAction> = {};
      for (const row of response.rows) {
        if (row.status === "duplicate") defaultActions[row.row_number] = "skip";
      }
      setActions(defaultActions);
    } catch {
      setError("Unable to parse this file. Confirm it's a CSV with the expected columns.");
    } finally {
      setIsBusy(false);
    }
  }

  function handleActionChange(rowNumber: number, action: ImportRowAction) {
    setActions((prev) => ({ ...prev, [rowNumber]: action }));
  }

  function handleBulkDuplicateAction(action: "skip" | "overwrite") {
    if (!preview) return;
    setActions((prev) => {
      const next = { ...prev };
      for (const row of preview.rows) {
        if (row.status === "duplicate") next[row.row_number] = action;
      }
      return next;
    });
  }

  async function handleConfirm() {
    if (!preview) return;
    setIsBusy(true);
    setError(null);
    try {
      const rows: ImportConfirmRow[] = preview.rows
        .filter((row) => row.status !== "invalid")
        .map((row) => ({
          row_number: row.row_number,
          well_id: row.well_id,
          record_date: row.record_date ?? "",
          oil_bopd: num(row.parsed.oil_bopd) ?? 0,
          gas_mscfd: num(row.parsed.gas_mscfd) ?? 0,
          water_bwpd: num(row.parsed.water_bwpd) ?? 0,
          choke_size: numOrNull(row.parsed.choke_size),
          wellhead_pressure: numOrNull(row.parsed.wellhead_pressure),
          tubing_pressure: numOrNull(row.parsed.tubing_pressure),
          casing_pressure: numOrNull(row.parsed.casing_pressure),
          flowline_pressure: numOrNull(row.parsed.flowline_pressure),
          wellhead_temperature: numOrNull(row.parsed.wellhead_temperature),
          action: row.status === "duplicate" ? (actions[row.row_number] ?? "skip") : "create",
        }));

      const response = await confirmProductionImport(rows);
      setResult(response);
    } catch {
      setError("Import failed. Try again.");
    } finally {
      setIsBusy(false);
    }
  }

  function handleReset() {
    setFile(null);
    setPreview(null);
    setResult(null);
    setError(null);
  }

  const importableCount = preview ? preview.rows.filter((r) => r.status !== "invalid").length : 0;

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title="Import Production Data"
        description="Upload a CSV, review the preview, then confirm — nothing is saved until you confirm."
      />

      {!preview && !result ? (
        <div className="flex flex-col gap-3 rounded-lg border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            Expected columns: <code>well_id,record_date,oil_bopd,gas_mscfd,water_bwpd,choke_size,
            wellhead_pressure,tubing_pressure,casing_pressure,flowline_pressure,wellhead_temperature</code>.
            Water cut, GOR, and BOE are calculated automatically — do not include them.
          </p>
          <input type="file" accept=".csv,text/csv" onChange={handleFileChange} className="text-sm" />
          <button
            type="button"
            onClick={handlePreview}
            disabled={!file || isBusy}
            className="w-fit rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
          >
            {isBusy ? "Uploading…" : "Preview"}
          </button>
        </div>
      ) : null}

      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

      {preview && !result ? (
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap gap-4 text-sm text-zinc-600 dark:text-zinc-400">
            <span>{preview.total_rows} rows</span>
            <span className="text-green-700 dark:text-green-400">{preview.valid_count} valid</span>
            <span className="text-amber-700 dark:text-amber-400">{preview.warning_count} warnings</span>
            <span className="text-blue-700 dark:text-blue-400">{preview.duplicate_count} duplicates</span>
            <span className="text-red-700 dark:text-red-400">{preview.invalid_count} invalid (excluded)</span>
          </div>

          <ImportPreviewTable
            rows={preview.rows}
            actions={actions}
            onActionChange={handleActionChange}
            onBulkDuplicateAction={handleBulkDuplicateAction}
          />

          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleConfirm}
              disabled={isBusy || importableCount === 0}
              className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
            >
              {isBusy ? "Importing…" : `Confirm Import (${importableCount} rows)`}
            </button>
            <button
              type="button"
              onClick={handleReset}
              className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
            >
              Start Over
            </button>
          </div>
        </div>
      ) : null}

      {result ? (
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap gap-4 text-sm">
            <span className="text-green-700 dark:text-green-400">{result.created} created</span>
            <span className="text-blue-700 dark:text-blue-400">{result.updated} updated</span>
            <span className="text-zinc-500 dark:text-zinc-400">{result.skipped} skipped</span>
            <span className="text-red-700 dark:text-red-400">{result.rejected.length} rejected</span>
          </div>

          {result.rejected.length > 0 ? (
            <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-xs dark:border-red-900 dark:bg-red-950/30">
              <p className="mb-2 font-medium text-red-800 dark:text-red-300">Rejected rows:</p>
              <ul className="space-y-1">
                {result.rejected.map((row) => (
                  <li key={row.row_number} className="text-red-700 dark:text-red-400">
                    Row {row.row_number} ({row.well_id}, {row.record_date}): {row.messages.join("; ")}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <button
            type="button"
            onClick={handleReset}
            className="w-fit rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
          >
            Import Another File
          </button>
        </div>
      ) : null}
    </div>
  );
}
