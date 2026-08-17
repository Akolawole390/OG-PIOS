"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import {
  exportProductionCsv,
  getCurrentUser,
  listFacilities,
  listProduction,
  listWells,
  type CurrentUser,
  type Facility,
  type ProductionEntry,
  type ProductionListResponse,
  type Well,
} from "@/lib/api";

const PAGE_SIZE = 25;
const CAN_MANAGE = new Set(["Administrator", "Production Engineer"]);

type SortField = "record_date" | "well_id" | "oil_bopd" | "gas_mscfd" | "water_bwpd";

export default function ProductionRecordsPage() {
  const [search, setSearch] = useState("");
  const [wellId, setWellId] = useState("");
  const [facilityId, setFacilityId] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [sort, setSort] = useState<SortField>("record_date");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1);

  const [data, setData] = useState<ProductionListResponse | null>(null);
  const [wells, setWells] = useState<Well[]>([]);
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);

  useEffect(() => {
    getCurrentUser().then(setCurrentUser).catch(() => undefined);
    listWells({ page_size: 100, sort: "well_id" }).then((res) => setWells(res.items)).catch(() => undefined);
    listFacilities().then(setFacilities).catch(() => undefined);
  }, []);

  useEffect(() => {
    const timeout = setTimeout(() => {
      setIsLoading(true);
      setError(null);
      listProduction({
        search: search || undefined,
        well_id: wellId ? Number(wellId) : undefined,
        facility_id: facilityId ? Number(facilityId) : undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        sort,
        order,
        page,
        page_size: PAGE_SIZE,
      })
        .then(setData)
        .catch(() => setError("Unable to load production records. Try again."))
        .finally(() => setIsLoading(false));
    }, 250);

    return () => clearTimeout(timeout);
  }, [search, wellId, facilityId, dateFrom, dateTo, sort, order, page]);

  function toggleSort(field: SortField) {
    if (sort === field) {
      setOrder((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSort(field);
      setOrder("desc");
    }
    setPage(1);
  }

  async function handleExport() {
    try {
      await exportProductionCsv({
        search: search || undefined,
        well_id: wellId ? Number(wellId) : undefined,
        facility_id: facilityId ? Number(facilityId) : undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      });
    } catch {
      setError("Export failed. Try again.");
    }
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const canManage = currentUser ? CAN_MANAGE.has(currentUser.role_name) : false;

  return (
    <div className="flex flex-1 flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <PageHeader title="Production Records" description="Daily production, pressure, and temperature entries." />
        <div className="flex shrink-0 gap-2">
          <button
            type="button"
            onClick={handleExport}
            className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
          >
            Export CSV
          </button>
          {canManage ? (
            <>
              <Link
                href="/production/import"
                className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
              >
                Import CSV
              </Link>
              <Link
                href="/production/records/new"
                className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
              >
                Add Record
              </Link>
            </>
          ) : null}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <input
          type="search"
          placeholder="Search well ID or name…"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          className="w-56 rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
        />
        <select
          value={wellId}
          onChange={(e) => {
            setWellId(e.target.value);
            setPage(1);
          }}
          className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
        >
          <option value="">All wells</option>
          {wells.map((w) => (
            <option key={w.id} value={w.id}>
              {w.well_id}
            </option>
          ))}
        </select>
        <select
          value={facilityId}
          onChange={(e) => {
            setFacilityId(e.target.value);
            setPage(1);
          }}
          className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
        >
          <option value="">All facilities</option>
          {facilities.map((f) => (
            <option key={f.id} value={f.id}>
              {f.name} ({f.field_name})
            </option>
          ))}
        </select>
        <input
          type="date"
          value={dateFrom}
          onChange={(e) => {
            setDateFrom(e.target.value);
            setPage(1);
          }}
          className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
        />
        <span className="text-sm text-zinc-400">to</span>
        <input
          type="date"
          value={dateTo}
          onChange={(e) => {
            setDateTo(e.target.value);
            setPage(1);
          }}
          className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
        />
      </div>

      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

      <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-zinc-200 bg-zinc-50 text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
              <SortableHeader field="record_date" label="Date" sort={sort} order={order} onSort={toggleSort} />
              <SortableHeader field="well_id" label="Well" sort={sort} order={order} onSort={toggleSort} />
              <th className="px-4 py-2 font-medium">Field / Facility</th>
              <SortableHeader field="oil_bopd" label="Oil (BOPD)" sort={sort} order={order} onSort={toggleSort} />
              <SortableHeader field="gas_mscfd" label="Gas (MSCFD)" sort={sort} order={order} onSort={toggleSort} />
              <SortableHeader field="water_bwpd" label="Water (BWPD)" sort={sort} order={order} onSort={toggleSort} />
              <th className="px-4 py-2 font-medium">Water Cut</th>
              <th className="px-4 py-2 font-medium">BOE</th>
              <th className="px-4 py-2 font-medium">Downtime</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={9} className="px-4 py-6 text-center text-zinc-500 dark:text-zinc-400">
                  Loading…
                </td>
              </tr>
            ) : !data || data.items.length === 0 ? (
              <tr>
                <td colSpan={9} className="px-4 py-6 text-center text-zinc-500 dark:text-zinc-400">
                  No production records found.
                </td>
              </tr>
            ) : (
              data.items.map((record: ProductionEntry) => (
                <tr
                  key={record.id}
                  className="border-b border-zinc-100 last:border-0 hover:bg-zinc-50 dark:border-zinc-900 dark:hover:bg-zinc-900"
                >
                  <td className="px-4 py-2">
                    <Link
                      href={`/production/records/${record.id}`}
                      className="font-medium text-zinc-900 hover:underline dark:text-zinc-50"
                    >
                      {record.record_date}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">{record.well_code}</td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">
                    {record.field_name} / {record.facility_name}
                  </td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">{record.oil_bopd.toLocaleString()}</td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">{record.gas_mscfd.toLocaleString()}</td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">{record.water_bwpd.toLocaleString()}</td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">
                    {record.water_cut_pct !== null ? `${record.water_cut_pct}%` : "—"}
                  </td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">{record.boe.toLocaleString()}</td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">
                    {record.downtime_hours > 0 ? `${record.downtime_hours}h` : "—"}
                  </td>
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
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="rounded-md border border-zinc-300 px-3 py-1 disabled:opacity-40 dark:border-zinc-700"
            >
              Previous
            </button>
            <button
              type="button"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="rounded-md border border-zinc-300 px-3 py-1 disabled:opacity-40 dark:border-zinc-700"
            >
              Next
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function SortableHeader({
  field,
  label,
  sort,
  order,
  onSort,
}: {
  field: SortField;
  label: string;
  sort: SortField;
  order: "asc" | "desc";
  onSort: (field: SortField) => void;
}) {
  const isActive = sort === field;
  return (
    <th className="px-4 py-2 font-medium">
      <button
        type="button"
        onClick={() => onSort(field)}
        className="flex items-center gap-1 hover:text-zinc-900 dark:hover:text-zinc-50"
      >
        {label}
        {isActive ? <span aria-hidden>{order === "asc" ? "▲" : "▼"}</span> : null}
      </button>
    </th>
  );
}
