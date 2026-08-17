"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import {
  getCurrentUser,
  listWells,
  type CurrentUser,
  type Well,
  type WellListResponse,
} from "@/lib/api";
import { formatLabel } from "@/lib/format";

const STATUS_OPTIONS = ["active", "shut_in", "suspended"];
const WELL_TYPE_OPTIONS = ["oil_producer", "gas_producer", "water_injector"];
const PAGE_SIZE = 25;
const CAN_MANAGE_WELLS = new Set(["Administrator", "Production Engineer"]);

type SortField = "well_id" | "name" | "status" | "well_type";

export default function WellsPage() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [wellType, setWellType] = useState("");
  const [sort, setSort] = useState<SortField>("well_id");
  const [order, setOrder] = useState<"asc" | "desc">("asc");
  const [page, setPage] = useState(1);

  const [data, setData] = useState<WellListResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);

  useEffect(() => {
    getCurrentUser()
      .then(setCurrentUser)
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    const timeout = setTimeout(() => {
      setIsLoading(true);
      setError(null);
      listWells({
        search: search || undefined,
        status: status || undefined,
        well_type: wellType || undefined,
        sort,
        order,
        page,
        page_size: PAGE_SIZE,
      })
        .then(setData)
        .catch(() => setError("Unable to load wells. Try again."))
        .finally(() => setIsLoading(false));
    }, 250);

    return () => clearTimeout(timeout);
  }, [search, status, wellType, sort, order, page]);

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
  const canManageWells = currentUser ? CAN_MANAGE_WELLS.has(currentUser.role_name) : false;

  return (
    <div className="flex flex-1 flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <PageHeader
          title="Wells"
          description="Well identification, production, pressure, and history."
        />
        {canManageWells ? (
          <Link
            href="/wells/new"
            className="shrink-0 rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
          >
            Add Well
          </Link>
        ) : null}
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
          className="w-64 rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
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
          value={wellType}
          onChange={(e) => {
            setWellType(e.target.value);
            setPage(1);
          }}
          className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
        >
          <option value="">All well types</option>
          {WELL_TYPE_OPTIONS.map((t) => (
            <option key={t} value={t}>
              {formatLabel(t)}
            </option>
          ))}
        </select>
      </div>

      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

      <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-zinc-200 bg-zinc-50 text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
              <SortableHeader field="well_id" label="Well ID" sort={sort} order={order} onSort={toggleSort} />
              <SortableHeader field="name" label="Name" sort={sort} order={order} onSort={toggleSort} />
              <SortableHeader field="well_type" label="Type" sort={sort} order={order} onSort={toggleSort} />
              <SortableHeader field="status" label="Status" sort={sort} order={order} onSort={toggleSort} />
              <th className="px-4 py-2 font-medium">Facility</th>
              <th className="px-4 py-2 font-medium">Field</th>
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
                  No wells found.
                </td>
              </tr>
            ) : (
              data.items.map((well: Well) => (
                <tr
                  key={well.id}
                  className="border-b border-zinc-100 last:border-0 hover:bg-zinc-50 dark:border-zinc-900 dark:hover:bg-zinc-900"
                >
                  <td className="px-4 py-2">
                    <Link href={`/wells/${well.id}`} className="font-medium text-zinc-900 hover:underline dark:text-zinc-50">
                      {well.well_id}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">{well.name}</td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">
                    {well.well_type ? formatLabel(well.well_type) : "—"}
                  </td>
                  <td className="px-4 py-2">
                    <StatusBadge status={well.status} />
                  </td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">{well.facility.name}</td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">{well.facility.field.name}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {data && data.total > 0 ? (
        <div className="flex items-center justify-between text-sm text-zinc-500 dark:text-zinc-400">
          <span>
            {data.total} well{data.total === 1 ? "" : "s"} — page {data.page} of {totalPages}
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
    active: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
    shut_in: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
    suspended: "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
  };
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
        styles[status] ?? styles.suspended
      }`}
    >
      {formatLabel(status)}
    </span>
  );
}
