"use client";

import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { listFacilities, type Facility, type WellPayload } from "@/lib/api";
import { formatLabel } from "@/lib/format";

const WELL_TYPE_OPTIONS = ["oil_producer", "gas_producer", "water_injector"];
const STATUS_OPTIONS = ["active", "shut_in", "suspended"];
const LIFT_TYPE_OPTIONS = ["ESP", "gas_lift", "rod_pump", "natural_flow"];
const COMPLETION_TYPE_OPTIONS = ["cased_hole", "open_hole", "gravel_pack"];

export type WellFormValues = {
  well_id: string;
  name: string;
  well_type: string;
  status: string;
  artificial_lift_type: string;
  latitude: string;
  longitude: string;
  facility_id: string;
  completion_date: string;
  completion_type: string;
  total_depth_ft: string;
};

const EMPTY_VALUES: WellFormValues = {
  well_id: "",
  name: "",
  well_type: "",
  status: "active",
  artificial_lift_type: "",
  latitude: "",
  longitude: "",
  facility_id: "",
  completion_date: "",
  completion_type: "",
  total_depth_ft: "",
};

type WellFormProps = {
  initialValues?: Partial<WellFormValues>;
  submitLabel: string;
  onSubmit: (payload: WellPayload) => Promise<void>;
};

export function WellForm({ initialValues, submitLabel, onSubmit }: WellFormProps) {
  const [values, setValues] = useState<WellFormValues>({ ...EMPTY_VALUES, ...initialValues });
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [errors, setErrors] = useState<Partial<Record<keyof WellFormValues, string>>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    listFacilities()
      .then(setFacilities)
      .catch(() => undefined);
  }, []);

  function update<K extends keyof WellFormValues>(key: K, value: WellFormValues[K]) {
    setValues((prev) => ({ ...prev, [key]: value }));
  }

  function validate(): boolean {
    const nextErrors: Partial<Record<keyof WellFormValues, string>> = {};
    if (!values.well_id.trim()) nextErrors.well_id = "Well ID is required.";
    if (!values.name.trim()) nextErrors.name = "Name is required.";
    if (!values.facility_id) nextErrors.facility_id = "Facility is required.";

    if (values.latitude) {
      const lat = Number(values.latitude);
      if (Number.isNaN(lat) || lat < -90 || lat > 90) {
        nextErrors.latitude = "Latitude must be between -90 and 90.";
      }
    }
    if (values.longitude) {
      const lon = Number(values.longitude);
      if (Number.isNaN(lon) || lon < -180 || lon > 180) {
        nextErrors.longitude = "Longitude must be between -180 and 180.";
      }
    }
    if (values.total_depth_ft) {
      const depth = Number(values.total_depth_ft);
      if (Number.isNaN(depth) || depth <= 0) {
        nextErrors.total_depth_ft = "Total depth must be a positive number.";
      }
    }

    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitError(null);
    if (!validate()) return;

    const payload: WellPayload = {
      well_id: values.well_id.trim(),
      name: values.name.trim(),
      well_type: values.well_type || null,
      status: values.status,
      artificial_lift_type: values.artificial_lift_type || null,
      latitude: values.latitude ? Number(values.latitude) : null,
      longitude: values.longitude ? Number(values.longitude) : null,
      facility_id: Number(values.facility_id),
      completion_date: values.completion_date || null,
      completion_type: values.completion_type || null,
      total_depth_ft: values.total_depth_ft ? Number(values.total_depth_ft) : null,
    };

    setIsSubmitting(true);
    try {
      await onSubmit(payload);
    } catch {
      setSubmitError("Unable to save well. Check the form and try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex max-w-2xl flex-col gap-5">
      <div className="grid grid-cols-2 gap-4">
        <Field label="Well ID" error={errors.well_id}>
          <input value={values.well_id} onChange={(e) => update("well_id", e.target.value)} className={inputClass} />
        </Field>
        <Field label="Name" error={errors.name}>
          <input value={values.name} onChange={(e) => update("name", e.target.value)} className={inputClass} />
        </Field>

        <Field label="Well Type">
          <select value={values.well_type} onChange={(e) => update("well_type", e.target.value)} className={inputClass}>
            <option value="">—</option>
            {WELL_TYPE_OPTIONS.map((t) => (
              <option key={t} value={t}>
                {formatLabel(t)}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Status">
          <select value={values.status} onChange={(e) => update("status", e.target.value)} className={inputClass}>
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {formatLabel(s)}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Artificial Lift">
          <select
            value={values.artificial_lift_type}
            onChange={(e) => update("artificial_lift_type", e.target.value)}
            className={inputClass}
          >
            <option value="">—</option>
            {LIFT_TYPE_OPTIONS.map((t) => (
              <option key={t} value={t}>
                {formatLabel(t)}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Facility" error={errors.facility_id}>
          <select
            value={values.facility_id}
            onChange={(e) => update("facility_id", e.target.value)}
            className={inputClass}
          >
            <option value="">Select a facility…</option>
            {facilities.map((f) => (
              <option key={f.id} value={f.id}>
                {f.name} ({f.field_name})
              </option>
            ))}
          </select>
        </Field>

        <Field label="Latitude" error={errors.latitude}>
          <input value={values.latitude} onChange={(e) => update("latitude", e.target.value)} className={inputClass} />
        </Field>
        <Field label="Longitude" error={errors.longitude}>
          <input value={values.longitude} onChange={(e) => update("longitude", e.target.value)} className={inputClass} />
        </Field>

        <Field label="Completion Date">
          <input
            type="date"
            value={values.completion_date}
            onChange={(e) => update("completion_date", e.target.value)}
            className={inputClass}
          />
        </Field>
        <Field label="Completion Type">
          <select
            value={values.completion_type}
            onChange={(e) => update("completion_type", e.target.value)}
            className={inputClass}
          >
            <option value="">—</option>
            {COMPLETION_TYPE_OPTIONS.map((t) => (
              <option key={t} value={t}>
                {formatLabel(t)}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Total Depth (ft)" error={errors.total_depth_ft}>
          <input
            value={values.total_depth_ft}
            onChange={(e) => update("total_depth_ft", e.target.value)}
            className={inputClass}
          />
        </Field>
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
  "mt-1 block w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900";

function Field({ label, error, children }: { label: string; error?: string; children: ReactNode }) {
  return (
    <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
      {label}
      {children}
      {error ? <span className="mt-1 block text-xs font-normal text-red-600 dark:text-red-400">{error}</span> : null}
    </label>
  );
}
