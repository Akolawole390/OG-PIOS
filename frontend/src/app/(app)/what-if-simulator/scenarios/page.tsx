"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { deleteScenario, listScenarios, type ScenarioListItem } from "@/lib/api";

const PAGE_SIZE = 25;

export default function SavedScenariosPage() {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<ScenarioListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<number[]>([]);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  function load() {
    setIsLoading(true);
    setError(null);
    listScenarios({ search: search || undefined, sort: "created_at", order: "desc", page, page_size: PAGE_SIZE })
      .then((res) => {
        setItems(res.items);
        setTotal(res.total);
      })
      .catch(() => setError("Unable to load saved scenarios. Try again."))
      .finally(() => setIsLoading(false));
  }

  useEffect(() => {
    const timeout = setTimeout(load, 250);
    return () => clearTimeout(timeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, page]);

  async function handleDelete(id: number) {
    if (!window.confirm("Delete this scenario? This cannot be undone.")) return;
    setDeletingId(id);
    try {
      await deleteScenario(id);
      load();
    } catch {
      setError("Unable to delete this scenario. Try again.");
    } finally {
      setDeletingId(null);
    }
  }

  function toggleSelected(id: number) {
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }

  function goCompare() {
    if (selected.length < 2) return;
    router.push(`/what-if-simulator/compare?ids=${selected.join(",")}`);
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="flex flex-1 flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <PageHeader title="Saved Scenarios" description="Every saved scenario stores the assumptions and calculation version used, for reproducibility." />
        <Link
          href="/what-if-simulator/builder"
          className="shrink-0 rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
        >
          New Scenario
        </Link>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <input
          type="search"
          placeholder="Search scenario name…"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          className="w-64 rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
        />
        <button
          type="button"
          onClick={goCompare}
          disabled={selected.length < 2}
          className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium hover:bg-zinc-100 disabled:opacity-40 dark:border-zinc-700 dark:hover:bg-zinc-900"
        >
          Compare Selected ({selected.length})
        </button>
      </div>

      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

      <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-zinc-200 bg-zinc-50 text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
              <th className="px-4 py-2 font-medium"></th>
              <th className="px-4 py-2 font-medium">Name</th>
              <th className="px-4 py-2 font-medium">Baseline Period</th>
              <th className="px-4 py-2 font-medium">Scope</th>
              <th className="px-4 py-2 font-medium">Created By</th>
              <th className="px-4 py-2 font-medium">Last Run</th>
              <th className="px-4 py-2 font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-zinc-500 dark:text-zinc-400">
                  Loading…
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-zinc-500 dark:text-zinc-400">
                  No saved scenarios yet.
                </td>
              </tr>
            ) : (
              items.map((item) => (
                <tr key={item.id} className="border-b border-zinc-100 last:border-0 hover:bg-zinc-50 dark:border-zinc-900 dark:hover:bg-zinc-900">
                  <td className="px-4 py-2">
                    <input type="checkbox" checked={selected.includes(item.id)} onChange={() => toggleSelected(item.id)} />
                  </td>
                  <td className="px-4 py-2">
                    <Link href={`/what-if-simulator/scenarios/${item.id}`} className="font-medium text-zinc-900 hover:underline dark:text-zinc-50">
                      {item.name}
                    </Link>
                    {item.description ? <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">{item.description}</p> : null}
                  </td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">
                    {item.baseline_date_from} to {item.baseline_date_to}
                  </td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">
                    {[item.field_name, item.facility_name, item.well_code, item.equipment_tag].filter(Boolean).join(" / ") || "All"}
                  </td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">{item.created_by_name ?? "—"}</td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">
                    {item.last_run_at ? item.last_run_at.slice(0, 19).replace("T", " ") : "Never"}
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
          <span>
            {total} scenario{total === 1 ? "" : "s"} — page {page} of {totalPages}
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
