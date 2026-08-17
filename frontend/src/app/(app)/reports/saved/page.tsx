"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { deleteReport, listReports, type ReportListItem } from "@/lib/api";
import { formatLabel } from "@/lib/format";

const PAGE_SIZE = 25;

export default function SavedReportsPage() {
  const [search, setSearch] = useState("");
  const [reportType, setReportType] = useState("");
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<ReportListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  function load() {
    setIsLoading(true);
    setError(null);
    listReports({ search: search || undefined, report_type: reportType || undefined, sort: "created_at", order: "desc", page, page_size: PAGE_SIZE })
      .then((res) => {
        setItems(res.items);
        setTotal(res.total);
      })
      .catch(() => setError("Unable to load saved reports. Try again."))
      .finally(() => setIsLoading(false));
  }

  useEffect(() => {
    const timeout = setTimeout(load, 250);
    return () => clearTimeout(timeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, reportType, page]);

  async function handleDelete(id: number) {
    if (!window.confirm("Delete this report? This cannot be undone.")) return;
    setDeletingId(id);
    try {
      await deleteReport(id);
      load();
    } catch {
      setError("Unable to delete this report. Try again.");
    } finally {
      setDeletingId(null);
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="flex flex-1 flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <PageHeader title="Saved Reports" description="Every saved report stores its filters and calculation version, for reproducibility." />
        <Link
          href="/reports/builder"
          className="shrink-0 rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
        >
          New Report
        </Link>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <input
          type="search"
          placeholder="Search report name…"
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          className="w-64 rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
        />
        <select
          value={reportType}
          onChange={(e) => { setReportType(e.target.value); setPage(1); }}
          className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
        >
          <option value="">All types</option>
          <option value="daily_operations">Daily Operations</option>
          <option value="weekly_production">Weekly Production</option>
          <option value="monthly_management">Monthly Management</option>
          <option value="what_if_scenario">What-If Scenario</option>
        </select>
      </div>

      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

      <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-zinc-200 bg-zinc-50 text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
              <th className="px-4 py-2 font-medium">Name</th>
              <th className="px-4 py-2 font-medium">Type</th>
              <th className="px-4 py-2 font-medium">Created By</th>
              <th className="px-4 py-2 font-medium">Last Generated</th>
              <th className="px-4 py-2 font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-zinc-500 dark:text-zinc-400">Loading…</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-zinc-500 dark:text-zinc-400">No saved reports yet.</td></tr>
            ) : (
              items.map((item) => (
                <tr key={item.id} className="border-b border-zinc-100 last:border-0 hover:bg-zinc-50 dark:border-zinc-900 dark:hover:bg-zinc-900">
                  <td className="px-4 py-2">
                    <Link href={`/reports/saved/${item.id}`} className="font-medium text-zinc-900 hover:underline dark:text-zinc-50">
                      {item.name}
                    </Link>
                    {item.description ? <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">{item.description}</p> : null}
                  </td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">{formatLabel(item.report_type)}</td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">{item.created_by_name ?? "—"}</td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">
                    {item.last_generated_at ? item.last_generated_at.slice(0, 19).replace("T", " ") : "Never"}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <button
                      type="button"
                      onClick={() => handleDelete(item.id)}
                      disabled={deletingId === item.id}
                      className="text-xs font-medium text-red-600 hover:underline disabled:opacity-40 dark:text-red-400"
                    >
                      {deletingId === item.id ? "Deleting…" : "Delete"}
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {total > 0 ? (
        <div className="flex items-center justify-between text-sm text-zinc-500 dark:text-zinc-400">
          <span>{total} report{total === 1 ? "" : "s"} — page {page} of {totalPages}</span>
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
