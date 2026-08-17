"use client";

import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import {
  listEquipment,
  listUsers,
  type CurrentUser,
  type Equipment,
  type MaintenancePayload,
  type MaintenancePriority,
  type MaintenanceStatus,
} from "@/lib/api";
import { formatLabel } from "@/lib/format";

const MAINTENANCE_TYPE_SUGGESTIONS = [
  "preventive",
  "corrective",
  "emergency",
  "predictive",
  "inspection",
  "calibration",
  "routine",
];

const STATUS_OPTIONS: MaintenanceStatus[] = [
  "scheduled",
  "open",
  "in_progress",
  "waiting_for_parts",
  "completed",
  "cancelled",
  "overdue",
];

const PRIORITY_OPTIONS: MaintenancePriority[] = ["critical", "high", "medium", "low"];

export type MaintenanceFormValues = {
  equipment_id: string;
  maintenance_type: string;
  priority: MaintenancePriority;
  status: MaintenanceStatus;
  description: string;
  planned_start_date: string;
  planned_completion_date: string;
  start_date: string;
  completion_date: string;
  technician_id: string;
  labor_cost: string;
  parts_cost: string;
  contractor_cost: string;
  other_cost: string;
  downtime_hours: string;
  failure_cause: string;
  corrective_action: string;
  notes: string;
};

const EMPTY_VALUES: MaintenanceFormValues = {
  equipment_id: "",
  maintenance_type: "",
  priority: "medium",
  status: "scheduled",
  description: "",
  planned_start_date: "",
  planned_completion_date: "",
  start_date: "",
  completion_date: "",
  technician_id: "",
  labor_cost: "",
  parts_cost: "",
  contractor_cost: "",
  other_cost: "",
  downtime_hours: "",
  failure_cause: "",
  corrective_action: "",
  notes: "",
};

const NUMERIC_FIELDS = ["labor_cost", "parts_cost", "contractor_cost", "other_cost", "downtime_hours"] as const;

type MaintenanceFormProps = {
  initialValues?: Partial<MaintenanceFormValues>;
  submitLabel: string;
  lockEquipment?: boolean;
  onSubmit: (payload: MaintenancePayload) => Promise<void>;
};

function toNumberOrNull(value: string): number | null {
  if (value.trim() === "") return null;
  const parsed = Number(value);
  return Number.isNaN(parsed) ? null : parsed;
}

export function MaintenanceForm({ initialValues, submitLabel, lockEquipment, onSubmit }: MaintenanceFormProps) {
  const [values, setValues] = useState<MaintenanceFormValues>({ ...EMPTY_VALUES, ...initialValues });
  const [equipmentOptions, setEquipmentOptions] = useState<Equipment[]>([]);
  const [technicians, setTechnicians] = useState<CurrentUser[]>([]);
  const [errors, setErrors] = useState<Partial<Record<keyof MaintenanceFormValues, string>>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    listEquipment({ page_size: 200, sort: "equipment_tag" }).then((res) => setEquipmentOptions(res.items)).catch(() => undefined);
    listUsers({ role: "Maintenance Engineer" }).then(setTechnicians).catch(() => undefined);
  }, []);

  function update<K extends keyof MaintenanceFormValues>(key: K, value: MaintenanceFormValues[K]) {
    setValues((prev) => ({ ...prev, [key]: value }));
  }

  function validate(): boolean {
    const nextErrors: Partial<Record<keyof MaintenanceFormValues, string>> = {};
    if (!values.equipment_id) nextErrors.equipment_id = "Equipment is required.";
    if (!values.maintenance_type.trim()) nextErrors.maintenance_type = "Maintenance type is required.";

    for (const field of NUMERIC_FIELDS) {
      const raw = values[field];
      if (raw.trim() !== "") {
        const parsed = Number(raw);
        if (Number.isNaN(parsed) || parsed < 0) {
          nextErrors[field] = "Must be zero or a positive number.";
        }
      }
    }

    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitError(null);
    if (!validate()) return;

    const payload: MaintenancePayload = {
      equipment_id: Number(values.equipment_id),
      maintenance_type: values.maintenance_type.trim(),
      priority: values.priority,
      status: values.status,
      description: values.description.trim() || null,
      planned_start_date: values.planned_start_date || null,
      planned_completion_date: values.planned_completion_date || null,
      start_date: values.start_date || null,
      completion_date: values.completion_date || null,
      technician_id: values.technician_id ? Number(values.technician_id) : null,
      labor_cost: toNumberOrNull(values.labor_cost),
      parts_cost: toNumberOrNull(values.parts_cost),
      contractor_cost: toNumberOrNull(values.contractor_cost),
      other_cost: toNumberOrNull(values.other_cost),
      downtime_hours: toNumberOrNull(values.downtime_hours),
      failure_cause: values.failure_cause.trim() || null,
      corrective_action: values.corrective_action.trim() || null,
      notes: values.notes.trim() || null,
    };

    setIsSubmitting(true);
    try {
      await onSubmit(payload);
    } catch (err) {
      setSubmitError(
        err instanceof Error ? err.message : "Unable to save this work order. Check the form and try again.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex max-w-2xl flex-col gap-5">
      <div className="grid grid-cols-2 gap-4">
        <Field label="Equipment" error={errors.equipment_id}>
          <select
            value={values.equipment_id}
            disabled={lockEquipment}
            onChange={(e) => update("equipment_id", e.target.value)}
            className={inputClass}
          >
            <option value="">Select equipment…</option>
            {equipmentOptions.map((e) => (
              <option key={e.id} value={e.id}>
                {e.equipment_tag} — {e.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Maintenance Type" error={errors.maintenance_type}>
          <input
            value={values.maintenance_type}
            onChange={(e) => update("maintenance_type", e.target.value)}
            list="maintenance-type-suggestions"
            className={inputClass}
          />
          <datalist id="maintenance-type-suggestions">
            {MAINTENANCE_TYPE_SUGGESTIONS.map((t) => (
              <option key={t} value={t} />
            ))}
          </datalist>
        </Field>

        <Field label="Priority">
          <select value={values.priority} onChange={(e) => update("priority", e.target.value as MaintenancePriority)} className={inputClass}>
            {PRIORITY_OPTIONS.map((p) => (
              <option key={p} value={p}>
                {formatLabel(p)}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Status">
          <select value={values.status} onChange={(e) => update("status", e.target.value as MaintenanceStatus)} className={inputClass}>
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {formatLabel(s)}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Assigned Technician">
          <select value={values.technician_id} onChange={(e) => update("technician_id", e.target.value)} className={inputClass}>
            <option value="">Unassigned</option>
            {technicians.map((t) => (
              <option key={t.id} value={t.id}>
                {t.full_name}
              </option>
            ))}
          </select>
        </Field>
        <div />

        <Field label="Planned Start Date">
          <input
            type="date"
            value={values.planned_start_date}
            onChange={(e) => update("planned_start_date", e.target.value)}
            className={inputClass}
          />
        </Field>
        <Field label="Planned Completion Date">
          <input
            type="date"
            value={values.planned_completion_date}
            onChange={(e) => update("planned_completion_date", e.target.value)}
            className={inputClass}
          />
        </Field>
        <Field label="Actual Start Date">
          <input type="date" value={values.start_date} onChange={(e) => update("start_date", e.target.value)} className={inputClass} />
        </Field>
        <Field label="Actual Completion Date">
          <input
            type="date"
            value={values.completion_date}
            onChange={(e) => update("completion_date", e.target.value)}
            className={inputClass}
          />
        </Field>

        <Field label="Labor Cost" error={errors.labor_cost}>
          <input value={values.labor_cost} onChange={(e) => update("labor_cost", e.target.value)} className={inputClass} />
        </Field>
        <Field label="Parts Cost" error={errors.parts_cost}>
          <input value={values.parts_cost} onChange={(e) => update("parts_cost", e.target.value)} className={inputClass} />
        </Field>
        <Field label="Contractor Cost" error={errors.contractor_cost}>
          <input value={values.contractor_cost} onChange={(e) => update("contractor_cost", e.target.value)} className={inputClass} />
        </Field>
        <Field label="Other Cost" error={errors.other_cost}>
          <input value={values.other_cost} onChange={(e) => update("other_cost", e.target.value)} className={inputClass} />
        </Field>

        <Field label="Downtime Hours" error={errors.downtime_hours}>
          <input value={values.downtime_hours} onChange={(e) => update("downtime_hours", e.target.value)} className={inputClass} />
        </Field>
      </div>

      <Field label="Description">
        <textarea value={values.description} onChange={(e) => update("description", e.target.value)} rows={2} className={inputClass} />
      </Field>
      <Field label="Failure Cause">
        <input value={values.failure_cause} onChange={(e) => update("failure_cause", e.target.value)} className={inputClass} />
      </Field>
      <Field label="Corrective Action">
        <textarea
          value={values.corrective_action}
          onChange={(e) => update("corrective_action", e.target.value)}
          rows={2}
          className={inputClass}
        />
      </Field>
      <Field label="Notes">
        <textarea value={values.notes} onChange={(e) => update("notes", e.target.value)} rows={2} className={inputClass} />
      </Field>

      <p className="text-xs text-zinc-500 dark:text-zinc-400">
        Total cost is calculated automatically from labor/parts/contractor/other cost — it is not entered
        directly. The work order number is assigned automatically on save.
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
