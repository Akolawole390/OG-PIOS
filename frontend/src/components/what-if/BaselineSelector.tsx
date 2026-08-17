"use client";

import { useEffect, useMemo, useState } from "react";
import { listEquipment, listFacilities, listWells, type BaselineConfig, type Equipment, type Facility, type Well } from "@/lib/api";

type BaselineSelectorProps = {
  value: BaselineConfig;
  onChange: (value: BaselineConfig) => void;
  disabled?: boolean;
};

const inputClass =
  "mt-1 block w-full rounded-md border border-zinc-300 px-3 py-2 text-sm disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900";

function toIntOrUndefined(value: string): number | undefined {
  if (value.trim() === "") return undefined;
  const parsed = Number(value);
  return Number.isNaN(parsed) ? undefined : Math.trunc(parsed);
}

/** Baseline period + scope picker shared by the Scenario Builder and Sensitivity Analysis
 * pages — the simulator never invents this data, it only selects which existing production/
 * cost/maintenance records the baseline is computed from. */
export function BaselineSelector({ value, onChange, disabled }: BaselineSelectorProps) {
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
        Baseline From
        <input
          type="date"
          disabled={disabled}
          value={value.date_from}
          onChange={(e) => onChange({ ...value, date_from: e.target.value })}
          className={inputClass}
        />
      </label>
      <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
        Baseline To
        <input
          type="date"
          disabled={disabled}
          value={value.date_to}
          onChange={(e) => onChange({ ...value, date_to: e.target.value })}
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

      <p className="col-span-full text-xs text-zinc-500 dark:text-zinc-400">
        Leave Field/Facility/Well/Equipment blank to scope the baseline to all data in the date range. The baseline
        is always computed from existing production, cost, and maintenance records — never invented.
      </p>
    </div>
  );
}
