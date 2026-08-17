"use client";

import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { listWells, type ProductionPayload, type Well } from "@/lib/api";

export type ProductionFormValues = {
  well_id: string;
  record_date: string;
  oil_bopd: string;
  gas_mscfd: string;
  water_bwpd: string;
  choke_size: string;
  wellhead_pressure: string;
  tubing_pressure: string;
  casing_pressure: string;
  flowline_pressure: string;
  wellhead_temperature: string;
};

const EMPTY_VALUES: ProductionFormValues = {
  well_id: "",
  record_date: "",
  oil_bopd: "0",
  gas_mscfd: "0",
  water_bwpd: "0",
  choke_size: "",
  wellhead_pressure: "",
  tubing_pressure: "",
  casing_pressure: "",
  flowline_pressure: "",
  wellhead_temperature: "",
};

type SubmitResult = { id: number; warnings?: string[] | null };

type ProductionFormProps = {
  initialValues?: Partial<ProductionFormValues>;
  submitLabel: string;
  lockWellAndDate?: boolean;
  onSubmit: (payload: ProductionPayload) => Promise<SubmitResult>;
  onSaved: (id: number) => void;
};

function toNumberOrUndefined(value: string): number | undefined {
  if (value.trim() === "") return undefined;
  const parsed = Number(value);
  return Number.isNaN(parsed) ? undefined : parsed;
}

function toNumberOrNull(value: string): number | null {
  if (value.trim() === "") return null;
  const parsed = Number(value);
  return Number.isNaN(parsed) ? null : parsed;
}

export function ProductionForm({
  initialValues,
  submitLabel,
  lockWellAndDate,
  onSubmit,
  onSaved,
}: ProductionFormProps) {
  const [values, setValues] = useState<ProductionFormValues>({ ...EMPTY_VALUES, ...initialValues });
  const [wells, setWells] = useState<Well[]>([]);
  const [errors, setErrors] = useState<Partial<Record<keyof ProductionFormValues, string>>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [savedId, setSavedId] = useState<number | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    listWells({ page_size: 100, sort: "well_id" })
      .then((res) => setWells(res.items))
      .catch(() => undefined);
  }, []);

  function update<K extends keyof ProductionFormValues>(key: K, value: ProductionFormValues[K]) {
    setValues((prev) => ({ ...prev, [key]: value }));
  }

  function validate(): boolean {
    const nextErrors: Partial<Record<keyof ProductionFormValues, string>> = {};
    if (!values.well_id) nextErrors.well_id = "Well is required.";
    if (!values.record_date) nextErrors.record_date = "Date is required.";

    for (const field of ["oil_bopd", "gas_mscfd", "water_bwpd"] as const) {
      const parsed = Number(values[field]);
      if (values[field].trim() !== "" && (Number.isNaN(parsed) || parsed < 0)) {
        nextErrors[field] = "Must be zero or a positive number.";
      }
    }

    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitError(null);
    setWarnings([]);
    if (!validate()) return;

    const payload: ProductionPayload = {
      well_id: Number(values.well_id),
      record_date: values.record_date,
      oil_bopd: toNumberOrUndefined(values.oil_bopd) ?? 0,
      gas_mscfd: toNumberOrUndefined(values.gas_mscfd) ?? 0,
      water_bwpd: toNumberOrUndefined(values.water_bwpd) ?? 0,
      choke_size: toNumberOrNull(values.choke_size),
      wellhead_pressure: toNumberOrNull(values.wellhead_pressure),
      tubing_pressure: toNumberOrNull(values.tubing_pressure),
      casing_pressure: toNumberOrNull(values.casing_pressure),
      flowline_pressure: toNumberOrNull(values.flowline_pressure),
      wellhead_temperature: toNumberOrNull(values.wellhead_temperature),
    };

    setIsSubmitting(true);
    try {
      const result = await onSubmit(payload);
      if (result.warnings && result.warnings.length > 0) {
        setWarnings(result.warnings);
        setSavedId(result.id);
      } else {
        onSaved(result.id);
      }
    } catch (err) {
      setSubmitError(
        err instanceof Error ? err.message : "Unable to save this record. Check the form and try again.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex max-w-2xl flex-col gap-5">
      <div className="grid grid-cols-2 gap-4">
        <Field label="Well" error={errors.well_id}>
          <select
            value={values.well_id}
            disabled={lockWellAndDate}
            onChange={(e) => update("well_id", e.target.value)}
            className={inputClass}
          >
            <option value="">Select a well…</option>
            {wells.map((w) => (
              <option key={w.id} value={w.id}>
                {w.well_id} — {w.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Date" error={errors.record_date}>
          <input
            type="date"
            value={values.record_date}
            disabled={lockWellAndDate}
            onChange={(e) => update("record_date", e.target.value)}
            className={inputClass}
          />
        </Field>

        <Field label="Oil (BOPD)" error={errors.oil_bopd}>
          <input value={values.oil_bopd} onChange={(e) => update("oil_bopd", e.target.value)} className={inputClass} />
        </Field>
        <Field label="Gas (MSCFD)" error={errors.gas_mscfd}>
          <input value={values.gas_mscfd} onChange={(e) => update("gas_mscfd", e.target.value)} className={inputClass} />
        </Field>
        <Field label="Water (BWPD)" error={errors.water_bwpd}>
          <input value={values.water_bwpd} onChange={(e) => update("water_bwpd", e.target.value)} className={inputClass} />
        </Field>
        <Field label="Choke Size">
          <input value={values.choke_size} onChange={(e) => update("choke_size", e.target.value)} className={inputClass} />
        </Field>

        <Field label="Wellhead Pressure (psi)">
          <input
            value={values.wellhead_pressure}
            onChange={(e) => update("wellhead_pressure", e.target.value)}
            className={inputClass}
          />
        </Field>
        <Field label="Tubing Pressure (psi)">
          <input
            value={values.tubing_pressure}
            onChange={(e) => update("tubing_pressure", e.target.value)}
            className={inputClass}
          />
        </Field>
        <Field label="Casing Pressure (psi)">
          <input
            value={values.casing_pressure}
            onChange={(e) => update("casing_pressure", e.target.value)}
            className={inputClass}
          />
        </Field>
        <Field label="Flowline Pressure (psi)">
          <input
            value={values.flowline_pressure}
            onChange={(e) => update("flowline_pressure", e.target.value)}
            className={inputClass}
          />
        </Field>

        <Field label="Wellhead Temperature (°F)">
          <input
            value={values.wellhead_temperature}
            onChange={(e) => update("wellhead_temperature", e.target.value)}
            className={inputClass}
          />
        </Field>
      </div>

      <p className="text-xs text-zinc-500 dark:text-zinc-400">
        Water cut, GOR, and BOE are calculated automatically from oil/gas/water — they are not
        entered directly.
      </p>

      {warnings.length > 0 ? (
        <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
          <p className="font-medium">Saved with warnings:</p>
          <ul className="mt-1 list-disc pl-4">
            {warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
          <button
            type="button"
            onClick={() => savedId !== null && onSaved(savedId)}
            className="mt-2 font-medium underline underline-offset-2"
          >
            Continue
          </button>
        </div>
      ) : null}

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
