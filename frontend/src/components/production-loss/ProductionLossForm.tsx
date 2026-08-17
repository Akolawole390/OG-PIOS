"use client";

import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import {
  listEquipment,
  listWells,
  type Equipment,
  type ProductionLossCategory,
  type ProductionLossPayload,
  type Well,
} from "@/lib/api";
import { formatLabel } from "@/lib/format";

const CATEGORY_OPTIONS: ProductionLossCategory[] = [
  "equipment_failure",
  "scheduled_maintenance",
  "reservoir",
  "weather",
  "operational",
  "market_curtailment",
  "other",
];

export type ProductionLossFormValues = {
  loss_date: string;
  category: ProductionLossCategory | "";
  cause: string;
  downtime_hours: string;
  well_id: string;
  equipment_id: string;
  downtime_event_id: string;
  maintenance_record_id: string;
  estimated_bopd_lost: string;
  estimated_mscf_lost: string;
  estimated_revenue_impact: string;
  currency: string;
};

const EMPTY_VALUES: ProductionLossFormValues = {
  loss_date: "",
  category: "",
  cause: "",
  downtime_hours: "",
  well_id: "",
  equipment_id: "",
  downtime_event_id: "",
  maintenance_record_id: "",
  estimated_bopd_lost: "",
  estimated_mscf_lost: "",
  estimated_revenue_impact: "",
  currency: "",
};

type ProductionLossFormProps = {
  initialValues?: Partial<ProductionLossFormValues>;
  submitLabel: string;
  onSubmit: (payload: ProductionLossPayload) => Promise<void>;
};

function toNumberOrNull(value: string): number | null {
  if (value.trim() === "") return null;
  const parsed = Number(value);
  return Number.isNaN(parsed) ? null : parsed;
}

function toIntOrNull(value: string): number | null {
  if (value.trim() === "") return null;
  const parsed = Number(value);
  return Number.isNaN(parsed) ? null : Math.trunc(parsed);
}

export function ProductionLossForm({ initialValues, submitLabel, onSubmit }: ProductionLossFormProps) {
  const [values, setValues] = useState<ProductionLossFormValues>({ ...EMPTY_VALUES, ...initialValues });
  const [wells, setWells] = useState<Well[]>([]);
  const [equipmentOptions, setEquipmentOptions] = useState<Equipment[]>([]);
  const [errors, setErrors] = useState<Partial<Record<keyof ProductionLossFormValues, string>>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    listWells({ page_size: 100, sort: "well_id" }).then((res) => setWells(res.items)).catch(() => undefined);
    listEquipment({ page_size: 200, sort: "equipment_tag" }).then((res) => setEquipmentOptions(res.items)).catch(() => undefined);
  }, []);

  function update<K extends keyof ProductionLossFormValues>(key: K, value: ProductionLossFormValues[K]) {
    setValues((prev) => ({ ...prev, [key]: value }));
  }

  function validate(): boolean {
    const nextErrors: Partial<Record<keyof ProductionLossFormValues, string>> = {};
    if (!values.loss_date) nextErrors.loss_date = "Loss date is required.";

    for (const field of ["downtime_hours", "estimated_bopd_lost", "estimated_mscf_lost", "estimated_revenue_impact"] as const) {
      const raw = values[field];
      if (raw.trim() !== "" && Number.isNaN(Number(raw))) {
        nextErrors[field] = "Must be a number.";
      }
    }

    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitError(null);
    if (!validate()) return;

    const payload: ProductionLossPayload = {
      loss_date: values.loss_date,
      category: values.category || null,
      cause: values.cause.trim() || null,
      downtime_hours: toNumberOrNull(values.downtime_hours),
      well_id: toIntOrNull(values.well_id),
      equipment_id: toIntOrNull(values.equipment_id),
      downtime_event_id: toIntOrNull(values.downtime_event_id),
      maintenance_record_id: toIntOrNull(values.maintenance_record_id),
      estimated_bopd_lost: toNumberOrNull(values.estimated_bopd_lost),
      estimated_mscf_lost: toNumberOrNull(values.estimated_mscf_lost),
      estimated_revenue_impact: toNumberOrNull(values.estimated_revenue_impact),
      currency: values.currency.trim() || null,
    };

    setIsSubmitting(true);
    try {
      await onSubmit(payload);
    } catch (err) {
      setSubmitError(
        err instanceof Error ? err.message : "Unable to save this production loss record. Check the form and try again.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex max-w-2xl flex-col gap-5">
      <div className="grid grid-cols-2 gap-4">
        <Field label="Loss Date" error={errors.loss_date}>
          <input type="date" value={values.loss_date} onChange={(e) => update("loss_date", e.target.value)} className={inputClass} />
        </Field>
        <Field label="Category">
          <select value={values.category} onChange={(e) => update("category", e.target.value as ProductionLossCategory)} className={inputClass}>
            <option value="">Uncategorized</option>
            {CATEGORY_OPTIONS.map((c) => (
              <option key={c} value={c}>
                {formatLabel(c)}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Well">
          <select value={values.well_id} onChange={(e) => update("well_id", e.target.value)} className={inputClass}>
            <option value="">None</option>
            {wells.map((w) => (
              <option key={w.id} value={w.id}>
                {w.well_id} — {w.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Equipment">
          <select value={values.equipment_id} onChange={(e) => update("equipment_id", e.target.value)} className={inputClass}>
            <option value="">None</option>
            {equipmentOptions.map((e) => (
              <option key={e.id} value={e.id}>
                {e.equipment_tag} — {e.name}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Downtime Event ID">
          <input value={values.downtime_event_id} onChange={(e) => update("downtime_event_id", e.target.value)} className={inputClass} />
        </Field>
        <Field label="Maintenance Record ID">
          <input value={values.maintenance_record_id} onChange={(e) => update("maintenance_record_id", e.target.value)} className={inputClass} />
        </Field>

        <Field label="Downtime Hours" error={errors.downtime_hours}>
          <input value={values.downtime_hours} onChange={(e) => update("downtime_hours", e.target.value)} className={inputClass} />
        </Field>
      </div>

      <Field label="Cause">
        <textarea value={values.cause} onChange={(e) => update("cause", e.target.value)} rows={2} className={inputClass} />
      </Field>

      <p className="text-xs text-zinc-500 dark:text-zinc-400">
        Downtime Event ID / Maintenance Record ID link this record to a specific investigated incident (preserves
        the audit trail — such a record can then only be edited, not deleted). Leave both blank for a general/
        manual estimate.
      </p>

      <div className="rounded-md border border-zinc-200 p-3 dark:border-zinc-800">
        <p className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
          Override Automatic Estimate (optional)
        </p>
        <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
          Normally left blank — lost volumes and revenue impact are calculated automatically from recorded
          production targets, actual production, and commodity prices for the well and date above. Fill these in
          only for a historical/manual entry that predates that data.
        </p>
        <div className="mt-3 grid grid-cols-2 gap-4">
          <Field label="Oil Lost (BOPD)" error={errors.estimated_bopd_lost}>
            <input value={values.estimated_bopd_lost} onChange={(e) => update("estimated_bopd_lost", e.target.value)} className={inputClass} />
          </Field>
          <Field label="Gas Lost (MSCFD)" error={errors.estimated_mscf_lost}>
            <input value={values.estimated_mscf_lost} onChange={(e) => update("estimated_mscf_lost", e.target.value)} className={inputClass} />
          </Field>
          <Field label="Revenue Impact" error={errors.estimated_revenue_impact}>
            <input value={values.estimated_revenue_impact} onChange={(e) => update("estimated_revenue_impact", e.target.value)} className={inputClass} />
          </Field>
          <Field label="Currency">
            <input value={values.currency} onChange={(e) => update("currency", e.target.value)} placeholder="USD" className={inputClass} />
          </Field>
        </div>
      </div>

      {submitError ? <p className="text-sm text-red-600 dark:text-red-400">{submitError}</p> : null}

      <button
        type="submit"
        disabled={isSubmitting}
        className="w-fit rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
      >
        {isSubmitting ? "Saving…" : submitLabel}
      </button>
    </form>
  );
}

const inputClass =
  "mt-1 block w-full rounded-md border border-zinc-300 px-3 py-2 text-sm disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900";

function Field({ label, error, children }: { label: string; error?: string; children: ReactNode }) {
  return (
    <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
      {label}
      {children}
      {error ? <span className="mt-1 block text-xs font-normal text-red-600 dark:text-red-400">{error}</span> : null}
    </label>
  );
}
