"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import {
  getCurrentUser,
  listEquipment,
  listFacilities,
  listWells,
  type CurrentUser,
  type Equipment,
  type EquipmentListResponse,
  type Facility,
  type Well,
} from "@/lib/api";
import { formatLabel } from "@/lib/format";

const STATUS_OPTIONS = ["operating", "standby", "maintenance", "failed", "decommissioned", "unknown"];
const PAGE_SIZE = 25;
const CAN_MANAGE = new Set(["Administrator", "Maintenance Engineer"]);

type SortField = "equipment_tag" | "name" | "equipment_type" | "status" | "health_score";

export default function EquipmentListPage() {
  const [search, setSearch] = useState("");
  const [equipmentType, setEquipmentType] = useState("");
  const [status, setStatus] = useState("");
  const [facilityId, setFacilityId] = useState("");
  const [wellId, setWellId] = useState("");
  const [sort, setSort] = useState<SortField>("equipment_tag");
  const [order, setOrder] = useState<"asc" | "desc">("asc");
  const [page, setPage] = useState(1);

  const [data, setData] = useState<EquipmentListResponse | null>(null);
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [wells, setWells] = useState<Well[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);

  useEffect(() => {
    getCurrentUser().then(setCurrentUser).catch(() => undefined);
    listFacilities().then(setFacilities).catch(() => undefined);
    listWells({ page_size: 100, sort: "well_id" }).then((res) => setWells(res.items)).catch(() => undefined);
  }, []);

  useEffect(() => {
    const timeout = setTimeout(() => {
      setIsLoading(true);
      setError(null);
      listEquipment({
        search: search || undefined,
        equipment_type: equipmentType || undefined,
        status: status || undefined,
        facility_id: facilityId ? Number(facilityId) : undefined,
        well_id: wellId ? Number(wellId) : undefined,
        sort,
        order,
        page,
        page_size: PAGE_SIZE,
      })
        .then(setData)
        .catch(() => setError("Unable to load equipment. Try again."))
        .finally(() => setIsLoading(false));
    }, 250);

    return () => clearTimeout(timeout);
  }, [search, equipmentType, status, facilityId, wellId, sort, order, page]);

  function toggleSort(field: SortField) {
    if (sort === field) {
      setOrder((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSort(field);
      setOrder("asc");
    }
    setPage(1);
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const canManage = currentUser ? CAN_MANAGE.has(currentUser.role_name) : false;

  return (
    <div className="flex flex-1 flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <PageHeader title="Equipment" description="Equipment inventory, association, and health status." />
        {canManage ? (
          <Link
            href="/equipment/new"
            className="shrink-0 rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
          >
            Add Equipment
          </Link>
        ) : null}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <input
          type="search"
          placeholder="Search tag or name…"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          className="w-56 rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
        />
        <input
          type="text"
          placeholder="Type…"
          value={equipmentType}
          onChange={(e) => {
            setEquipmentType(e.target.value);
            setPage(1);
          }}
          className="w-32 rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
        />
        <select
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(1);
          }}
          className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
        >
          <option value="">All statuses</option>
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {formatLabel(s)}
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
      </div>

      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

      <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-zinc-200 bg-zinc-50 text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
              <SortableHeader field="equipment_tag" label="Tag" sort={sort} order={order} onSort={toggleSort} />
              <SortableHeader field="name" label="Name" sort={sort} order={order} onSort={toggleSort} />
              <SortableHeader field="equipment_type" label="Type" sort={sort} order={order} onSort={toggleSort} />
              <th className="px-4 py-2 font-medium">Field / Facility / Well</th>
              <SortableHeader field="status" label="Status" sort={sort} order={order} onSort={toggleSort} />
              <SortableHeader field="health_score" label="Health" sort={sort} order={order} onSort={toggleSort} />
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
                  No equipment found.
                </td>
              </tr>
            ) : (
              data.items.map((item: Equipment) => (
                <tr
                  key={item.id}
                  className="border-b border-zinc-100 last:border-0 hover:bg-zinc-50 dark:border-zinc-900 dark:hover:bg-zinc-900"
                >
                  <td className="px-4 py-2">
                    <Link
                      href={`/equipment/${item.id}`}
                      className="font-medium text-zinc-900 hover:underline dark:text-zinc-50"
                    >
                      {item.equipment_tag}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">{item.name}</td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">{formatLabel(item.equipment_type)}</td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">
                    {item.field_name ? `${item.field_name} / ${item.facility_name}` : "—"}
                    {item.well_code ? ` / ${item.well_code}` : ""}
                  </td>
                  <td className="px-4 py-2">
                    <StatusBadge status={item.status} />
                  </td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">
                    {item.health_score !== null ? (
                      <span>
                        {item.health_score.toFixed(0)}{" "}
                        <span className="text-xs text-zinc-500 dark:text-zinc-400">({item.health_band})</span>
                      </span>
                    ) : (
                      "—"
                    )}
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
            {data.total} item{data.total === 1 ? "" : "s"} — page {data.page} of {totalPages}
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

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    operating: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
    standby: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
    maintenance: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
    failed: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
    decommissioned: "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
    unknown: "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
  };
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
        styles[status] ?? styles.unknown
      }`}
    >
      {formatLabel(status)}
    </span>
  );
}
