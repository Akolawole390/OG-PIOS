"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { MaintenanceTable } from "@/components/maintenance/MaintenanceTable";
import {
  getCurrentUser,
  listEquipment,
  listFacilities,
  listMaintenance,
  listWells,
  type CurrentUser,
  type Equipment,
  type Facility,
  type MaintenanceListResponse,
  type Well,
} from "@/lib/api";

const STATUS_OPTIONS = ["scheduled", "open", "in_progress", "waiting_for_parts", "completed", "cancelled", "overdue"];
const PRIORITY_OPTIONS = ["critical", "high", "medium", "low"];
const PAGE_SIZE = 25;
const CAN_MANAGE = new Set(["Administrator", "Maintenance Engineer"]);

export default function MaintenanceListPage() {
  const [search, setSearch] = useState("");
  const [equipmentId, setEquipmentId] = useState("");
  const [wellId, setWellId] = useState("");
  const [facilityId, setFacilityId] = useState("");
  const [fieldId, setFieldId] = useState("");
  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");
  const [maintenanceType, setMaintenanceType] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);

  const [data, setData] = useState<MaintenanceListResponse | null>(null);
  const [equipmentOptions, setEquipmentOptions] = useState<Equipment[]>([]);
  const [wells, setWells] = useState<Well[]>([]);
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);

  const fields = useMemo(() => {
    const map = new Map<number, string>();
    for (const f of facilities) {
      // Facility doesn't carry field_id as a number key elsewhere, so this list is built
      // purely for the filter dropdown from whatever facilities/fields are already loaded.
      if (!map.has(f.field_id)) map.set(f.field_id, f.field_name);
    }
    return Array.from(map.entries()).map(([id, name]) => ({ id, name }));
  }, [facilities]);

  useEffect(() => {
    getCurrentUser().then(setCurrentUser).catch(() => undefined);
    listEquipment({ page_size: 200, sort: "equipment_tag" }).then((res) => setEquipmentOptions(res.items)).catch(() => undefined);
    listWells({ page_size: 100, sort: "well_id" }).then((res) => setWells(res.items)).catch(() => undefined);
    listFacilities().then(setFacilities).catch(() => undefined);
  }, []);

  useEffect(() => {
    const timeout = setTimeout(() => {
      setIsLoading(true);
      setError(null);
      listMaintenance({
        search: search || undefined,
        equipment_id: equipmentId ? Number(equipmentId) : undefined,
        well_id: wellId ? Number(wellId) : undefined,
        facility_id: facilityId ? Number(facilityId) : undefined,
        field_id: fieldId ? Number(fieldId) : undefined,
        status: status || undefined,
        priority: priority || undefined,
        maintenance_type: maintenanceType || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        page,
        page_size: PAGE_SIZE,
      })
        .then(setData)
        .catch(() => setError("Unable to load maintenance records. Try again."))
        .finally(() => setIsLoading(false));
    }, 250);

    return () => clearTimeout(timeout);
  }, [search, equipmentId, wellId, facilityId, fieldId, status, priority, maintenanceType, dateFrom, dateTo, page]);

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const canManage = currentUser ? CAN_MANAGE.has(currentUser.role_name) : false;

  return (
    <div className="flex flex-1 flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <PageHeader title="Maintenance Records" description="Full maintenance and work-order history." />
        {canManage ? (
          <Link
            href="/maintenance/new"
            className="shrink-0 rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
          >
            Create Work Order
          </Link>
        ) : null}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <input
          type="search"
          placeholder="Search description or work order…"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          className="w-56 rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
        />
        <select value={equipmentId} onChange={(e) => { setEquipmentId(e.target.value); setPage(1); }} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          <option value="">All equipment</option>
          {equipmentOptions.map((e) => (
            <option key={e.id} value={e.id}>{e.equipment_tag}</option>
          ))}
        </select>
        <select value={wellId} onChange={(e) => { setWellId(e.target.value); setPage(1); }} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          <option value="">All wells</option>
          {wells.map((w) => (
            <option key={w.id} value={w.id}>{w.well_id}</option>
          ))}
        </select>
        <select value={facilityId} onChange={(e) => { setFacilityId(e.target.value); setPage(1); }} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          <option value="">All facilities</option>
          {facilities.map((f) => (
            <option key={f.id} value={f.id}>{f.name}</option>
          ))}
        </select>
        <select value={fieldId} onChange={(e) => { setFieldId(e.target.value); setPage(1); }} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          <option value="">All fields</option>
          {fields.map((f) => (
            <option key={f.id} value={f.id}>{f.name}</option>
          ))}
        </select>
        <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          <option value="">All statuses</option>
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <select value={priority} onChange={(e) => { setPriority(e.target.value); setPage(1); }} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          <option value="">All priorities</option>
          {PRIORITY_OPTIONS.map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
        <input
          type="text"
          placeholder="Type…"
          value={maintenanceType}
          onChange={(e) => { setMaintenanceType(e.target.value); setPage(1); }}
          className="w-28 rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
        />
        <input type="date" value={dateFrom} onChange={(e) => { setDateFrom(e.target.value); setPage(1); }} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900" />
        <span className="text-sm text-zinc-400">to</span>
        <input type="date" value={dateTo} onChange={(e) => { setDateTo(e.target.value); setPage(1); }} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900" />
      </div>

      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

      <MaintenanceTable items={data?.items ?? []} isLoading={isLoading} emptyMessage="No maintenance records found." />

      {data && data.total > 0 ? (
        <div className="flex items-center justify-between text-sm text-zinc-500 dark:text-zinc-400">
          <span>
            {data.total} record{data.total === 1 ? "" : "s"} — page {data.page} of {totalPages}
          </span>
          <div className="flex gap-2">
            <button type="button" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1} className="rounded-md border border-zinc-300 px-3 py-1 disabled:opacity-40 dark:border-zinc-700">
              Previous
            </button>
            <button type="button" onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages} className="rounded-md border border-zinc-300 px-3 py-1 disabled:opacity-40 dark:border-zinc-700">
              Next
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
