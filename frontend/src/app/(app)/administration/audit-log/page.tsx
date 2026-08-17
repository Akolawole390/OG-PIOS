"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { AdminGuard } from "@/components/administration/AdminGuard";
import { AuditLogTable } from "@/components/administration/AuditLogTable";
import { formatLabel } from "@/lib/format";
import { listAuditLog, type AuditLogEntry } from "@/lib/api";

const PAGE_SIZE = 25;

const KNOWN_ACTIONS = [
  "user_created",
  "user_updated",
  "user_activated",
  "user_deactivated",
  "role_changed",
  "system_setting_changed",
  "report_generated",
  "whatif_scenario_created",
  "ai_insight_run",
];

export default function AuditLogPage() {
  const [search, setSearch] = useState("");
  const [action, setAction] = useState("");
  const [resource, setResource] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<AuditLogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<AuditLogEntry | null>(null);

  function load() {
    setIsLoading(true);
    setError(null);
    listAuditLog({
      search: search || undefined,
      action: action || undefined,
      resource: resource || undefined,
      date_from: dateFrom ? `${dateFrom}T00:00:00` : undefined,
      date_to: dateTo ? `${dateTo}T23:59:59` : undefined,
      page,
      page_size: PAGE_SIZE,
    })
      .then((res) => {
        setItems(res.items);
        setTotal(res.total);
      })
      .catch(() => setError("Unable to load the audit log. Try again."))
      .finally(() => setIsLoading(false));
  }

  useEffect(() => {
    const timeout = setTimeout(load, 250);
    return () => clearTimeout(timeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, action, resource, dateFrom, dateTo, page]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <AdminGuard>
      <div className="flex flex-1 flex-col gap-6">
        <PageHeader
          title="Audit Log"
          description="A read-only record of user management, role changes, system settings, and other administrative and system activity."
        />

        <div className="flex flex-wrap items-center gap-3">
          <input
            type="search"
            placeholder="Search action or details…"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="w-64 rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          />
          <select
            value={action}
            onChange={(e) => { setAction(e.target.value); setPage(1); }}
            className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          >
            <option value="">All actions</option>
            {KNOWN_ACTIONS.map((a) => (
              <option key={a} value={a}>{formatLabel(a)}</option>
            ))}
          </select>
          <input
            placeholder="Resource type (e.g. user)"
            value={resource}
            onChange={(e) => { setResource(e.target.value); setPage(1); }}
            className="w-44 rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          />
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => { setDateFrom(e.target.value); setPage(1); }}
            className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          />
          <span className="text-xs text-zinc-400">to</span>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => { setDateTo(e.target.value); setPage(1); }}
            className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          />
        </div>

        {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

        {isLoading ? (
          <p className="text-sm text-zinc-500 dark:text-zinc-400">Loading…</p>
        ) : (
          <AuditLogTable items={items} onSelect={setSelected} />
        )}

        {total > 0 ? (
          <div className="flex items-center justify-between text-sm text-zinc-500 dark:text-zinc-400">
            <span>{total} event{total === 1 ? "" : "s"} — page {page} of {totalPages}</span>
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

        {selected ? (
          <div className="fixed inset-0 z-10 flex items-center justify-center bg-black/40 p-4" onClick={() => setSelected(null)}>
            <div
              className="w-full max-w-lg rounded-lg border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950"
              onClick={(e) => e.stopPropagation()}
            >
              <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">{formatLabel(selected.action)}</h3>
              <dl className="mt-3 flex flex-col gap-2 text-sm">
                <Row label="Event ID" value={String(selected.id)} />
                <Row label="User" value={selected.user_email ?? "System"} />
                <Row label="Resource" value={selected.entity_type ? formatLabel(selected.entity_type) : "—"} />
                <Row label="Resource ID" value={selected.entity_id !== null ? String(selected.entity_id) : "—"} />
                <Row label="Status" value={formatLabel(selected.status)} />
                <Row label="Timestamp" value={selected.created_at.slice(0, 19).replace("T", " ")} />
                {selected.details ? <Row label="Details" value={selected.details} /> : null}
                {selected.metadata_json ? (
                  <Row label="Metadata" value={JSON.stringify(selected.metadata_json)} />
                ) : null}
              </dl>
              <button
                type="button"
                onClick={() => setSelected(null)}
                className="mt-4 rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
              >
                Close
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </AdminGuard>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="shrink-0 text-zinc-500 dark:text-zinc-400">{label}</dt>
      <dd className="break-all text-right text-zinc-900 dark:text-zinc-50">{value}</dd>
    </div>
  );
}
