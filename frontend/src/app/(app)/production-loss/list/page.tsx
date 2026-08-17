"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import {
  getCurrentUser,
  listEquipment,
  listProductionLoss,
  listWells,
  type CurrentUser,
  type Equipment,
  type ProductionLossListResponse,
  type Well,
} from "@/lib/api";
import { formatCurrency, formatLabel } from "@/lib/format";

const CATEGORY_OPTIONS = [
  "equipment_failure",
  "scheduled_maintenance",
  "reservoir",
  "weather",
  "operational",
  "market_curtailment",
  "other",
];
const PAGE_SIZE = 25;
const CAN_MANAGE = new Set(["Administrator", "Production Engineer"]);

export default function ProductionLossListPage() {
  const [search, setSearch] = useState("");
  const [wellId, setWellId] = useState("");
  const [equipmentId, setEquipmentId] = useState("");
  const [category, setCategory] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);

  const [data, setData] = useState<ProductionLossListResponse | null>(null);
  const [wells, setWells] = useState<Well[]>([]);
  const [equipmentOptions, setEquipmentOptions] = useState<Equipment[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);

  useEffect(() => {
    getCurrentUser().then(setCurrentUser).catch(() => undefined);
    listWells({ page_size: 100, sort: "well_id" }).then((res) => setWells(res.items)).catch(() => undefined);
    listEquipment({ page_size: 200, sort: "equipment_tag" }).then((res) => setEquipmentOptions(res.items)).catch(() => undefined);
  }, []);

  useEffect(() => {
    const timeout = setTimeout(() => {
      setIsLoading(true);
      setError(null);
      listProductionLoss({
        search: search || undefined,
        well_id: wellId ? Number(wellId) : undefined,
        equipment_id: equipmentId ? Number(equipmentId) : undefined,
        category: category || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        page,
        page_size: PAGE_SIZE,
      })
        .then(setData)
        .catch(() => setError("Unable to load production loss records. Try again."))
        .finally(() => setIsLoading(false));
    }, 250);

    return () => clearTimeout(timeout);
  }, [search, wellId, equipmentId, category, dateFrom, dateTo, page]);

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const canManage = currentUser ? CAN_MANAGE.has(currentUser.role_name) : false;

  return (
    <div className="flex flex-1 flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <PageHeader title="Production Loss Records" description="Estimated production loss and financial impact history." />
        {canManage ? (
          <Link
            href="/production-loss/new"
            className="shrink-0 rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
          >
            Add Record
          </Link>
        ) : null}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <input
          type="search"
          placeholder="Search cause…"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          className="w-56 rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
        />
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
        <select value={category} onChange={(e) => { setCategory(e.target.value); setPage(1); }} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          <option value="">All categories</option>
          {CATEGORY_OPTIONS.map((c) => (
            <option key={c} value={c}>{formatLabel(c)}</option>
          ))}
        </select>
        <input type="date" value={dateFrom} onChange={(e) => { setDateFrom(e.target.value); setPage(1); }} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900" />
        <span className="text-sm text-zinc-400">to</span>
        <input type="date" value={dateTo} onChange={(e) => { setDateTo(e.target.value); setPage(1); }} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900" />
      </div>

      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

      <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-zinc-200 bg-zinc-50 text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
              <th className="px-4 py-2 font-medium">Date</th>
              <th className="px-4 py-2 font-medium">Well / Equipment</th>
              <th className="px-4 py-2 font-medium">Category</th>
              <th className="px-4 py-2 font-medium">Oil Lost (bbl)</th>
              <th className="px-4 py-2 font-medium">Gas Lost (mscf)</th>
              <th className="px-4 py-2 font-medium">Revenue Impact</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-zinc-500 dark:text-zinc-400">
                  Loading…
                </td>
              </tr>
            ) : !data || data.items.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-zinc-500 dark:text-zinc-400">
                  No production loss records found.
                </td>
              </tr>
            ) : (
              data.items.map((item) => (
                <tr key={item.id} className="border-b border-zinc-100 last:border-0 hover:bg-zinc-50 dark:border-zinc-900 dark:hover:bg-zinc-900">
                  <td className="px-4 py-2">
                    <Link href={`/production-loss/${item.id}`} className="font-medium text-zinc-900 hover:underline dark:text-zinc-50">
                      {item.loss_date}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">
                    {[item.well_code, item.equipment_tag].filter(Boolean).join(" / ") || "—"}
                  </td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">{item.category ? formatLabel(item.category) : "—"}</td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">{item.estimated_bopd_lost ?? "—"}</td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">{item.estimated_mscf_lost ?? "—"}</td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">{formatCurrency(item.estimated_revenue_impact, item.currency)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

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
