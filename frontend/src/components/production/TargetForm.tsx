"use client";

import { useEffect, useState, type FormEvent } from "react";
import { listWells, type ProductionTargetPayload, type Well } from "@/lib/api";

type TargetFormProps = {
  onSubmit: (payload: ProductionTargetPayload) => Promise<void>;
};

export function TargetForm({ onSubmit }: TargetFormProps) {
  const [wells, setWells] = useState<Well[]>([]);
  const [wellId, setWellId] = useState("");
  const [effectiveDate, setEffectiveDate] = useState("");
  const [oilTarget, setOilTarget] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    listWells({ page_size: 100, sort: "well_id" }).then((res) => setWells(res.items)).catch(() => undefined);
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (!wellId || !effectiveDate) {
      setError("Well and effective date are required.");
      return;
    }
    setIsSubmitting(true);
    try {
      await onSubmit({
        well_id: Number(wellId),
        effective_date: effectiveDate,
        oil_target_bopd: oilTarget.trim() === "" ? null : Number(oilTarget),
      });
      setWellId("");
      setEffectiveDate("");
      setOilTarget("");
    } catch {
      setError("Unable to save this target.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
        Well
        <select
          value={wellId}
          onChange={(e) => setWellId(e.target.value)}
          className="mt-1 block rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
        >
          <option value="">Select a well…</option>
          {wells.map((w) => (
            <option key={w.id} value={w.id}>{w.well_id}</option>
          ))}
        </select>
      </label>
      <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
        Effective Date
        <input
          type="date"
          value={effectiveDate}
          onChange={(e) => setEffectiveDate(e.target.value)}
          className="mt-1 block rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
        />
      </label>
      <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
        Oil Target (BOPD)
        <input
          value={oilTarget}
          onChange={(e) => setOilTarget(e.target.value)}
          className="mt-1 block rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
        />
      </label>
      <button
        type="submit"
        disabled={isSubmitting}
        className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
      >
        {isSubmitting ? "Saving…" : "Add Target"}
      </button>
      {error ? <p className="w-full text-sm text-red-600 dark:text-red-400">{error}</p> : null}
    </form>
  );
}
