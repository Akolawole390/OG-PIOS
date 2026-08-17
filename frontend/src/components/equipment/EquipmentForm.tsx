"use client";

import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { listFacilities, listWells, type EquipmentPayload, type EquipmentStatus, type Facility, type Well } from "@/lib/api";
import { formatLabel } from "@/lib/format";

const EQUIPMENT_TYPE_SUGGESTIONS = [
  "ESP",
  "gas_lift",
  "rod_pump",
  "compressor",
  "generator",
  "separator",
  "heat_exchanger",
  "valve",
  "motor",
  "instrumentation",
  "other",
];

const STATUS_OPTIONS: EquipmentStatus[] = ["operating", "standby", "maintenance", "failed", "decommissioned", "unknown"];

export type EquipmentFormValues = {
  equipment_tag: string;
  name: string;
  equipment_type: string;
  manufacturer: string;
  model: string;
  serial_number: string;
  installation_date: string;
  commissioning_date: string;
  description: string;
  status: EquipmentStatus;
  operating_hours: string;
  next_maintenance_due: string;
  facility_id: string;
  well_id: string;
};

const EMPTY_VALUES: EquipmentFormValues = {
  equipment_tag: "",
  name: "",
  equipment_type: "",
  manufacturer: "",
  model: "",
  serial_number: "",
  installation_date: "",
  commissioning_date: "",
  description: "",
  status: "unknown",
  operating_hours: "",
  next_maintenance_due: "",
  facility_id: "",
  well_id: "",
};

type EquipmentFormProps = {
  initialValues?: Partial<EquipmentFormValues>;
  submitLabel: string;
  onSubmit: (payload: EquipmentPayload) => Promise<void>;
};

export function EquipmentForm({ initialValues, submitLabel, onSubmit }: EquipmentFormProps) {
  const [values, setValues] = useState<EquipmentFormValues>({ ...EMPTY_VALUES, ...initialValues });
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [wells, setWells] = useState<Well[]>([]);
  const [errors, setErrors] = useState<Partial<Record<keyof EquipmentFormValues, string>>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    listFacilities().then(setFacilities).catch(() => undefined);
    listWells({ page_size: 100, sort: "well_id" }).then((res) => setWells(res.items)).catch(() => undefined);
  }, []);

  function update<K extends keyof EquipmentFormValues>(key: K, value: EquipmentFormValues[K]) {
    setValues((prev) => ({ ...prev, [key]: value }));
  }

  function validate(): boolean {
    const nextErrors: Partial<Record<keyof EquipmentFormValues, string>> = {};
    if (!values.equipment_tag.trim()) nextErrors.equipment_tag = "Equipment tag is required.";
    if (!values.name.trim()) nextErrors.name = "Name is required.";
    if (!values.equipment_type.trim()) nextErrors.equipment_type = "Equipment type is required.";

    if (values.operating_hours) {
      const hours = Number(values.operating_hours);
      if (Number.isNaN(hours) || hours < 0) {
        nextErrors.operating_hours = "Operating hours must be zero or a positive number.";
      }
    }

    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitError(null);
    if (!validate()) return;

    const payload: EquipmentPayload = {
      equipment_tag: values.equipment_tag.trim(),
      name: values.name.trim(),
      equipment_type: values.equipment_type.trim(),
      manufacturer: values.manufacturer.trim() || null,
      model: values.model.trim() || null,
      serial_number: values.serial_number.trim() || null,
      installation_date: values.installation_date || null,
      commissioning_date: values.commissioning_date || null,
      description: values.description.trim() || null,
      status: values.status,
      operating_hours: values.operating_hours ? Number(values.operating_hours) : null,
      next_maintenance_due: values.next_maintenance_due || null,
      facility_id: values.facility_id ? Number(values.facility_id) : null,
      well_id: values.well_id ? Number(values.well_id) : null,
    };

    setIsSubmitting(true);
    try {
      await onSubmit(payload);
    } catch (err) {
      setSubmitError(
        err instanceof Error ? err.message : "Unable to save this equipment record. Check the form and try again.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex max-w-2xl flex-col gap-5">
      <div className="grid grid-cols-2 gap-4">
        <Field label="Equipment Tag" error={errors.equipment_tag}>
          <input
            value={values.equipment_tag}
            onChange={(e) => update("equipment_tag", e.target.value)}
            className={inputClass}
          />
        </Field>
        <Field label="Name" error={errors.name}>
          <input value={values.name} onChange={(e) => update("name", e.target.value)} className={inputClass} />
        </Field>

        <Field label="Equipment Type" error={errors.equipment_type}>
          <input
            value={values.equipment_type}
            onChange={(e) => update("equipment_type", e.target.value)}
            list="equipment-type-suggestions"
            className={inputClass}
          />
          <datalist id="equipment-type-suggestions">
            {EQUIPMENT_TYPE_SUGGESTIONS.map((t) => (
              <option key={t} value={t} />
            ))}
          </datalist>
        </Field>
        <Field label="Status">
          <select value={values.status} onChange={(e) => update("status", e.target.value as EquipmentStatus)} className={inputClass}>
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {formatLabel(s)}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Manufacturer">
          <input value={values.manufacturer} onChange={(e) => update("manufacturer", e.target.value)} className={inputClass} />
        </Field>
        <Field label="Model">
          <input value={values.model} onChange={(e) => update("model", e.target.value)} className={inputClass} />
        </Field>
        <Field label="Serial Number">
          <input value={values.serial_number} onChange={(e) => update("serial_number", e.target.value)} className={inputClass} />
        </Field>
        <Field label="Operating Hours" error={errors.operating_hours}>
          <input value={values.operating_hours} onChange={(e) => update("operating_hours", e.target.value)} className={inputClass} />
        </Field>

        <Field label="Installation Date">
          <input
            type="date"
            value={values.installation_date}
            onChange={(e) => update("installation_date", e.target.value)}
            className={inputClass}
          />
        </Field>
        <Field label="Commissioning Date">
          <input
            type="date"
            value={values.commissioning_date}
            onChange={(e) => update("commissioning_date", e.target.value)}
            className={inputClass}
          />
        </Field>
        <Field label="Next Maintenance Due">
          <input
            type="date"
            value={values.next_maintenance_due}
            onChange={(e) => update("next_maintenance_due", e.target.value)}
            className={inputClass}
          />
        </Field>

        <Field label="Facility">
          <select value={values.facility_id} onChange={(e) => update("facility_id", e.target.value)} className={inputClass}>
            <option value="">None</option>
            {facilities.map((f) => (
              <option key={f.id} value={f.id}>
                {f.name} ({f.field_name})
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
      </div>

      <Field label="Description">
        <textarea
          value={values.description}
          onChange={(e) => update("description", e.target.value)}
          rows={3}
          className={inputClass}
        />
      </Field>

      <p className="text-xs text-zinc-500 dark:text-zinc-400">
        Equipment may be associated with a well, a facility, or neither. If both a facility and a well are
        set, the well&apos;s facility/field is used to resolve location. Health score is computed
        automatically from operating data and cannot be entered directly.
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
