"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { AlertSeverityBadge } from "@/components/alerts/AlertSeverityBadge";
import { AlertStatusBadge } from "@/components/alerts/AlertStatusBadge";
import {
  getCurrentUser,
  listAlerts,
  listEquipment,
  listFacilities,
  listWells,
  type AlertListResponse,
  type CurrentUser,
  type Equipment,
  type Facility,
  type Well,
} from "@/lib/api";

const SEVERITY_OPTIONS = ["critical", "high", "medium", "low", "informational"];
const CATEGORY_OPTIONS = ["production", "equipment", "maintenance", "production_loss", "economics"];
const STATUS_OPTIONS = ["new", "acknowledged", "investigating", "resolved", "dismissed"];
const PAGE_SIZE = 25;
const CAN_MANAGE = new Set(["Administrator", "Management"]);

export default function AlertsListPage() {
  const [search, setSearch] = useState("");
  const [severity, setSeverity] = useState("");
  const [category, setCategory] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [fieldId, setFieldId] = useState("");
  const [wellId, setWellId] = useState("");
  const [equipmentId, setEquipmentId] = useState("");
  const [page, setPage] = useState(1);

  const [data, setData] = useState<AlertListResponse | null>(null);
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [wells, setWells] = useState<Well[]>([]);
  const [equipmentOptions, setEquipmentOptions] = useState<Equipment[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);

  useEffect(() => {
    getCurrentUser().then(setCurrentUser).catch(() => undefined);
    listFacilities().then(setFacilities).catch(() => undefined);
    listWells({ page_size: 100, sort: "well_id" }).then((res) => setWells(res.items)).catch(() => undefined);
    listEquipment({ page_size: 200, sort: "equipment_tag" }).then((res) => setEquipmentOptions(res.items)).catch(() => undefined);
  }, []);

  useEffect(() => {
    const timeout = setTimeout(() => {
      setIsLoading(true);
      setError(null);
      listAlerts({
        search: search || undefined,
        severity: severity || undefined,
        category: category || undefined,
        status: statusFilter || undefined,
        well_id: wellId ? Number(wellId) : undefined,
        equipment_id: equipmentId ? Number(equipmentId) : undefined,
        field_id: fieldId ? Number(fieldId) : undefined,
        page,
        page_size: PAGE_SIZE,
      })
        .then(setData)
        .catch(() => setError("Unable to load alerts. Try again."))
        .finally(() => setIsLoading(false));
    }, 250);
    return () => clearTimeout(timeout);
  }, [search, severity, category, statusFilter, fieldId, wellId, equipmentId, page]);

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const canManage = currentUser ? CAN_MANAGE.has(currentUser.role_name) : false;

  const fields = Array.from(new Map(facilities.map((f) => [f.field_id, f.field_name])).entries());

  return (
    <div className="flex flex-1 flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <PageHeader title="Alerts" description="Search, filter, and manage alerts across every module." />
        {canManage ? (
          <Link
            href="/alerts/new"
            className="shrink-0 rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
          >
            Add Alert
          </Link>
        ) : null}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <input
          type="search"
          placeholder="Search title/description…"
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          className="w-56 rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
        />
        <select value={severity} onChange={(e) => { setSeverity(e.target.value); setPage(1); }} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          <option value="">All severities</option>
          {SEVERITY_OPTIONS.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <select value={category} onChange={(e) => { setCategory(e.target.value); setPage(1); }} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          <option value="">All categories</option>
          {CATEGORY_OPTIONS.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          <option value="">All statuses</option>
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <select value={fieldId} onChange={(e) => { setFieldId(e.target.value); setPage(1); }} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          <option value="">All fields</option>
          {fields.map(([id, name]) => (
            <option key={id} value={id}>{name}</option>
          ))}
        </select>
        <select value={wellId} onChange={(e) => { setWellId(e.target.value); setPage(1); }} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          <option value="">All wells</option>
          {wells.map((w) => (
            <option key={w.id} value={w.id}>{w.well_id}</option>
          ))}
        </select>
        <select value={equipmentId} onChange={(e) => { setEquipmentId(e.target.value); setPage(1); }} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          <option value="">All equipment</option>
          {equipmentOptions.map((e) => (
            <option key={e.id} value={e.id}>{e.equipment_tag}</option>
          ))}
        </select>
      </div>

      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

      <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-zinc-200 bg-zinc-50 text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
              <th className="px-4 py-2 font-medium">Triggered</th>
              <th className="px-4 py-2 font-medium">Title</th>
              <th className="px-4 py-2 font-medium">Category</th>
              <th className="px-4 py-2 font-medium">Severity</th>
              <th className="px-4 py-2 font-medium">Status</th>
              <th className="px-4 py-2 font-medium">Affected</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr><td colSpan={6} className="px-4 py-6 text-center text-zinc-500 dark:text-zinc-400">Loading…</td></tr>
            ) : !data || data.items.length === 0 ? (
              <tr><td colSpan={6} className="px-4 py-6 text-center text-zinc-500 dark:text-zinc-400">No alerts found.</td></tr>
            ) : (
              data.items.map((alert) => (
                <tr key={alert.id} className="border-b border-zinc-100 last:border-0 hover:bg-zinc-50 dark:border-zinc-900 dark:hover:bg-zinc-900">
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">{alert.triggered_at.slice(0, 10)}</td>
                  <td className="px-4 py-2">
                    <Link href={`/alerts/${alert.id}`} className="font-medium text-zinc-900 hover:underline dark:text-zinc-50">
                      {alert.title}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">{alert.category}</td>
                  <td className="px-4 py-2"><AlertSeverityBadge severity={alert.severity} /></td>
                  <td className="px-4 py-2"><AlertStatusBadge status={alert.status} /></td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">
                    {[alert.field_name, alert.well_code, alert.equipment_tag].filter(Boolean).join(" / ") || "—"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {data && data.total > 0 ? (
        <div className="flex items-center justify-between text-sm text-zinc-500 dark:text-zinc-400">
          <span>{data.total} alert{data.total === 1 ? "" : "s"} — page {data.page} of {totalPages}</span>
          <div className="flex gap-2">
            <button type="button" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1} className="rounded-md border border-zinc-300 px-3 py-1 disabled:opacity-40 dark:border-zinc-700">Previous</button>
            <button type="button" onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages} className="rounded-md border border-zinc-300 px-3 py-1 disabled:opacity-40 dark:border-zinc-700">Next</button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
