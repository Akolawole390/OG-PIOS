"use client";

import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import {
  listEquipment,
  listFacilities,
  listWells,
  type CostCurrency,
  type Equipment,
  type Facility,
  type OperatingCostPayload,
  type Well,
} from "@/lib/api";

const CATEGORY_SUGGESTIONS = [
  "Production",
  "Maintenance",
  "Energy",
  "Chemicals",
  "Labour",
  "Contractor",
  "Logistics",
  "Utilities",
  "Facility",
  "Equipment",
  "Other",
];

const CURRENCY_OPTIONS: CostCurrency[] = ["USD", "NGN"];
const COST_PERIOD_SUGGESTIONS = ["monthly", "one_time", "daily"];
const SOURCE_SUGGESTIONS = ["invoice", "estimate", "manual_entry"];

export type OperatingCostFormValues = {
  cost_date: string;
  category: string;
  amount: string;
  currency: CostCurrency;
  description: string;
  cost_period: string;
  source: string;
  notes: string;
  field_id: string;
  facility_id: string;
  well_id: string;
  equipment_id: string;
};

const EMPTY_VALUES: OperatingCostFormValues = {
  cost_date: "",
  category: "",
  amount: "",
  currency: "USD",
  description: "",
  cost_period: "",
  source: "",
  notes: "",
  field_id: "",
  facility_id: "",
  well_id: "",
  equipment_id: "",
};

type OperatingCostFormProps = {
  initialValues?: Partial<OperatingCostFormValues>;
  submitLabel: string;
  onSubmit: (payload: OperatingCostPayload) => Promise<void>;
};

function toIntOrNull(value: string): number | null {
  if (value.trim() === "") return null;
  const parsed = Number(value);
  return Number.isNaN(parsed) ? null : Math.trunc(parsed);
}

export function OperatingCostForm({ initialValues, submitLabel, onSubmit }: OperatingCostFormProps) {
  const [values, setValues] = useState<OperatingCostFormValues>({ ...EMPTY_VALUES, ...initialValues });
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [wells, setWells] = useState<Well[]>([]);
  const [equipmentOptions, setEquipmentOptions] = useState<Equipment[]>([]);
  const [errors, setErrors] = useState<Partial<Record<keyof OperatingCostFormValues, string>>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    listFacilities().then(setFacilities).catch(() => undefined);
    listWells({ page_size: 100, sort: "well_id" }).then((res) => setWells(res.items)).catch(() => undefined);
    listEquipment({ page_size: 200, sort: "equipment_tag" }).then((res) => setEquipmentOptions(res.items)).catch(() => undefined);
  }, []);

  const fields = useMemo(() => {
    const map = new Map<number, string>();
    for (const f of facilities) {
      if (!map.has(f.field_id)) map.set(f.field_id, f.field_name);
    }
    return Array.from(map.entries()).map(([id, name]) => ({ id, name }));
  }, [facilities]);

  function update<K extends keyof OperatingCostFormValues>(key: K, value: OperatingCostFormValues[K]) {
    setValues((prev) => ({ ...prev, [key]: value }));
  }

  function validate(): boolean {
    const nextErrors: Partial<Record<keyof OperatingCostFormValues, string>> = {};
    if (!values.cost_date) nextErrors.cost_date = "Cost date is required.";
    if (!values.category.trim()) nextErrors.category = "Category is required.";

    const amount = Number(values.amount);
    if (values.amount.trim() === "" || Number.isNaN(amount)) {
      nextErrors.amount = "Amount is required and must be a number.";
    } else if (amount < 0) {
      nextErrors.amount = "Amount cannot be negative.";
    }

    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitError(null);
    if (!validate()) return;

    const payload: OperatingCostPayload = {
      cost_date: values.cost_date,
      category: values.category.trim(),
      amount: Number(values.amount),
      currency: values.currency,
      description: values.description.trim() || null,
      cost_period: values.cost_period.trim() || null,
      source: values.source.trim() || null,
      notes: values.notes.trim() || null,
      field_id: toIntOrNull(values.field_id),
      facility_id: toIntOrNull(values.facility_id),
      well_id: toIntOrNull(values.well_id),
      equipment_id: toIntOrNull(values.equipment_id),
    };

    setIsSubmitting(true);
    try {
      await onSubmit(payload);
    } catch (err) {
      setSubmitError(
        err instanceof Error ? err.message : "Unable to save this operating cost record. Check the form and try again.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex max-w-2xl flex-col gap-5">
      <div className="grid grid-cols-2 gap-4">
        <Field label="Cost Date" error={errors.cost_date}>
          <input type="date" value={values.cost_date} onChange={(e) => update("cost_date", e.target.value)} className={inputClass} />
        </Field>
        <Field label="Category" error={errors.category}>
          <input
            value={values.category}
            onChange={(e) => update("category", e.target.value)}
            list="cost-category-suggestions"
            className={inputClass}
          />
          <datalist id="cost-category-suggestions">
            {CATEGORY_SUGGESTIONS.map((c) => (
              <option key={c} value={c} />
            ))}
          </datalist>
        </Field>

        <Field label="Amount" error={errors.amount}>
          <input value={values.amount} onChange={(e) => update("amount", e.target.value)} className={inputClass} />
        </Field>
        <Field label="Currency">
          <select value={values.currency} onChange={(e) => update("currency", e.target.value as CostCurrency)} className={inputClass}>
            {CURRENCY_OPTIONS.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </Field>

        <Field label="Field">
          <select value={values.field_id} onChange={(e) => update("field_id", e.target.value)} className={inputClass}>
            <option value="">None</option>
            {fields.map((f) => (
              <option key={f.id} value={f.id}>{f.name}</option>
            ))}
          </select>
        </Field>
        <Field label="Facility">
          <select value={values.facility_id} onChange={(e) => update("facility_id", e.target.value)} className={inputClass}>
            <option value="">None</option>
            {facilities.map((f) => (
              <option key={f.id} value={f.id}>{f.name} ({f.field_name})</option>
            ))}
          </select>
        </Field>

        <Field label="Well">
          <select value={values.well_id} onChange={(e) => update("well_id", e.target.value)} className={inputClass}>
            <option value="">None</option>
            {wells.map((w) => (
              <option key={w.id} value={w.id}>{w.well_id} — {w.name}</option>
            ))}
          </select>
        </Field>
        <Field label="Equipment">
          <select value={values.equipment_id} onChange={(e) => update("equipment_id", e.target.value)} className={inputClass}>
            <option value="">None</option>
            {equipmentOptions.map((e) => (
              <option key={e.id} value={e.id}>{e.equipment_tag} — {e.name}</option>
            ))}
          </select>
        </Field>

        <Field label="Cost Period">
          <input value={values.cost_period} onChange={(e) => update("cost_period", e.target.value)} list="cost-period-suggestions" className={inputClass} />
          <datalist id="cost-period-suggestions">
            {COST_PERIOD_SUGGESTIONS.map((p) => (
              <option key={p} value={p} />
            ))}
          </datalist>
        </Field>
        <Field label="Source">
          <input value={values.source} onChange={(e) => update("source", e.target.value)} list="cost-source-suggestions" className={inputClass} />
          <datalist id="cost-source-suggestions">
            {SOURCE_SUGGESTIONS.map((s) => (
              <option key={s} value={s} />
            ))}
          </datalist>
        </Field>
      </div>

      <Field label="Description">
        <input value={values.description} onChange={(e) => update("description", e.target.value)} className={inputClass} />
      </Field>
      <Field label="Notes">
        <textarea value={values.notes} onChange={(e) => update("notes", e.target.value)} rows={2} className={inputClass} />
      </Field>

      <p className="text-xs text-zinc-500 dark:text-zinc-400">
        Do not require a well or equipment for field/facility-level costs — leave those blank unless this cost is
        specific to one well or piece of equipment.
      </p>

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
