"use client";

import { useEffect, useMemo, useState } from "react";
import { listEquipment, listFacilities, listWells, type Equipment, type Facility, type ReportFilters, type Well } from "@/lib/api";

const MAINTENANCE_TYPE_OPTIONS = ["preventive", "corrective", "emergency", "inspection"];
const ALERT_SEVERITY_OPTIONS = ["critical", "high", "medium", "low", "informational"];
const PRODUCTION_LOSS_CATEGORY_OPTIONS = [
  "equipment_failure", "scheduled_maintenance", "reservoir", "weather", "operational", "market_curtailment", "other",
];
const COMMODITY_OPTIONS = ["oil", "gas"];

const inputClass =
  "mt-1 block w-full rounded-md border border-zinc-300 px-3 py-2 text-sm disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900";

type ReportFilterFormProps = {
  value: ReportFilters;
  onChange: (value: ReportFilters) => void;
  disabled?: boolean;
};

function toIntOrUndefined(value: string): number | undefined {
  if (value.trim() === "") return undefined;
  const parsed = Number(value);
  return Number.isNaN(parsed) ? undefined : Math.trunc(parsed);
}

/** The full section-4 filter set (date range, field/facility/well/equipment, commodity,
 * maintenance type, alert severity, production-loss category) — the same filters apply
 * consistently across every section of a report, per the module spec. Not used for the What-If
 * Scenario Report, which selects a saved scenario instead (see the builder page). */
export function ReportFilterForm({ value, onChange, disabled }: ReportFilterFormProps) {
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [wells, setWells] = useState<Well[]>([]);
  const [equipmentOptions, setEquipmentOptions] = useState<Equipment[]>([]);

  useEffect(() => {
    listFacilities().then(setFacilities).catch(() => undefined);
    listWells({ page_size: 200, sort: "well_id" }).then((res) => setWells(res.items)).catch(() => undefined);
    listEquipment({ page_size: 200, sort: "equipment_tag" }).then((res) => setEquipmentOptions(res.items)).catch(() => undefined);
  }, []);

  const fields = useMemo(() => {
    const map = new Map<number, string>();
    for (const f of facilities) {
      if (!map.has(f.field_id)) map.set(f.field_id, f.field_name);
    }
    return Array.from(map.entries()).map(([id, name]) => ({ id, name }));
  }, [facilities]);

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
        Date From
        <input
          type="date"
          disabled={disabled}
          value={value.date_from ?? ""}
          onChange={(e) => onChange({ ...value, date_from: e.target.value || undefined })}
          className={inputClass}
        />
      </label>
      <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
        Date To
        <input
          type="date"
          disabled={disabled}
          value={value.date_to ?? ""}
          onChange={(e) => onChange({ ...value, date_to: e.target.value || undefined })}
          className={inputClass}
        />
      </label>
      <div />

      <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
        Field
        <select
          disabled={disabled}
          value={value.field_id ?? ""}
          onChange={(e) => onChange({ ...value, field_id: toIntOrUndefined(e.target.value) ?? null })}
          className={inputClass}
        >
          <option value="">All fields</option>
          {fields.map((f) => (
            <option key={f.id} value={f.id}>{f.name}</option>
          ))}
        </select>
      </label>
      <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
        Facility
        <select
          disabled={disabled}
          value={value.facility_id ?? ""}
          onChange={(e) => onChange({ ...value, facility_id: toIntOrUndefined(e.target.value) ?? null })}
          className={inputClass}
        >
          <option value="">Any facility</option>
          {facilities.map((f) => (
            <option key={f.id} value={f.id}>{f.name} ({f.field_name})</option>
          ))}
        </select>
      </label>
      <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
        Well
        <select
          disabled={disabled}
          value={value.well_id ?? ""}
          onChange={(e) => onChange({ ...value, well_id: toIntOrUndefined(e.target.value) ?? null })}
          className={inputClass}
        >
          <option value="">Any well</option>
          {wells.map((w) => (
            <option key={w.id} value={w.id}>{w.well_id} — {w.name}</option>
          ))}
        </select>
      </label>

      <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
        Equipment
        <select
          disabled={disabled}
          value={value.equipment_id ?? ""}
          onChange={(e) => onChange({ ...value, equipment_id: toIntOrUndefined(e.target.value) ?? null })}
          className={inputClass}
        >
          <option value="">Any equipment</option>
          {equipmentOptions.map((eq) => (
            <option key={eq.id} value={eq.id}>{eq.equipment_tag} — {eq.name}</option>
          ))}
        </select>
      </label>
      <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
        Commodity
        <select
          disabled={disabled}
          value={value.commodity ?? ""}
          onChange={(e) => onChange({ ...value, commodity: e.target.value || undefined })}
          className={inputClass}
        >
          <option value="">Oil &amp; Gas</option>
          {COMMODITY_OPTIONS.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </label>
      <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
        Maintenance Type
        <select
          disabled={disabled}
          value={value.maintenance_type ?? ""}
          onChange={(e) => onChange({ ...value, maintenance_type: e.target.value || undefined })}
          className={inputClass}
        >
          <option value="">Any type</option>
          {MAINTENANCE_TYPE_OPTIONS.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </label>

      <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
        Alert Severity
        <select
          disabled={disabled}
          value={value.alert_severity ?? ""}
          onChange={(e) => onChange({ ...value, alert_severity: e.target.value || undefined })}
          className={inputClass}
        >
          <option value="">Any severity</option>
          {ALERT_SEVERITY_OPTIONS.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </label>
      <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
        Production Loss Category
        <select
          disabled={disabled}
          value={value.production_loss_category ?? ""}
          onChange={(e) => onChange({ ...value, production_loss_category: e.target.value || undefined })}
          className={inputClass}
        >
          <option value="">Any category</option>
          {PRODUCTION_LOSS_CATEGORY_OPTIONS.map((c) => (
            <option key={c} value={c}>{c.replace(/_/g, " ")}</option>
          ))}
        </select>
      </label>

      <p className="col-span-full text-xs text-zinc-500 dark:text-zinc-400">
        These filters apply consistently across every section of the report. Leave any field
        blank for &ldquo;no restriction&rdquo; on that dimension.
      </p>
    </div>
  );
}
