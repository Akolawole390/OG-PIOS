"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { ConfidenceBadge } from "@/components/ai-insights/ConfidenceBadge";
import { InsightStatusBadge } from "@/components/ai-insights/InsightStatusBadge";
import { AlertSeverityBadge } from "@/components/alerts/AlertSeverityBadge";
import {
  listEquipment,
  listFacilities,
  listInsights,
  listWells,
  type Equipment,
  type Facility,
  type InsightListResponse,
  type Well,
} from "@/lib/api";

const SEVERITY_OPTIONS = ["critical", "high", "medium", "low", "informational"];
const CATEGORY_OPTIONS = ["production", "equipment", "maintenance", "production_loss", "economics", "cross_domain", "optimization"];
const STATUS_OPTIONS = ["new", "reviewed", "dismissed"];
const CONFIDENCE_OPTIONS = ["high", "medium", "low"];
const PAGE_SIZE = 25;

export default function AiInsightsListPage() {
  const [search, setSearch] = useState("");
  const [severity, setSeverity] = useState("");
  const [category, setCategory] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [confidence, setConfidence] = useState("");
  const [fieldId, setFieldId] = useState("");
  const [wellId, setWellId] = useState("");
  const [equipmentId, setEquipmentId] = useState("");
  const [page, setPage] = useState(1);

  const [data, setData] = useState<InsightListResponse | null>(null);
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [wells, setWells] = useState<Well[]>([]);
  const [equipmentOptions, setEquipmentOptions] = useState<Equipment[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listFacilities().then(setFacilities).catch(() => undefined);
    listWells({ page_size: 100, sort: "well_id" }).then((res) => setWells(res.items)).catch(() => undefined);
    listEquipment({ page_size: 200, sort: "equipment_tag" }).then((res) => setEquipmentOptions(res.items)).catch(() => undefined);
  }, []);

  useEffect(() => {
    const timeout = setTimeout(() => {
      setIsLoading(true);
      setError(null);
      listInsights({
        search: search || undefined,
        severity: severity || undefined,
        category: category || undefined,
        status: statusFilter || undefined,
        confidence_level: confidence || undefined,
        well_id: wellId ? Number(wellId) : undefined,
        equipment_id: equipmentId ? Number(equipmentId) : undefined,
        field_id: fieldId ? Number(fieldId) : undefined,
        page,
        page_size: PAGE_SIZE,
      })
        .then(setData)
        .catch(() => setError("Unable to load insights. Try again."))
        .finally(() => setIsLoading(false));
    }, 250);
    return () => clearTimeout(timeout);
  }, [search, severity, category, statusFilter, confidence, fieldId, wellId, equipmentId, page]);

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const fields = Array.from(new Map(facilities.map((f) => [f.field_id, f.field_name])).entries());

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader title="AI Insights" description="Search and filter evidence-based insights across every module." />

      <div className="flex flex-wrap items-center gap-3">
        <input
          type="search"
          placeholder="Search title/summary…"
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
        <select value={confidence} onChange={(e) => { setConfidence(e.target.value); setPage(1); }} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          <option value="">All confidence levels</option>
          {CONFIDENCE_OPTIONS.map((c) => (
            <option key={c} value={c}>{c}</option>
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
              <th className="px-4 py-2 font-medium">Generated</th>
              <th className="px-4 py-2 font-medium">Title</th>
              <th className="px-4 py-2 font-medium">Category</th>
              <th className="px-4 py-2 font-medium">Severity</th>
              <th className="px-4 py-2 font-medium">Confidence</th>
              <th className="px-4 py-2 font-medium">Status</th>
              <th className="px-4 py-2 font-medium">Affected</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr><td colSpan={7} className="px-4 py-6 text-center text-zinc-500 dark:text-zinc-400">Loading…</td></tr>
            ) : !data || data.items.length === 0 ? (
              <tr><td colSpan={7} className="px-4 py-6 text-center text-zinc-500 dark:text-zinc-400">No insights found.</td></tr>
            ) : (
              data.items.map((insight) => (
                <tr key={insight.id} className="border-b border-zinc-100 last:border-0 hover:bg-zinc-50 dark:border-zinc-900 dark:hover:bg-zinc-900">
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">{insight.generated_at.slice(0, 10)}</td>
                  <td className="px-4 py-2">
                    <Link href={`/ai-insights/${insight.id}`} className="font-medium text-zinc-900 hover:underline dark:text-zinc-50">
                      {insight.title}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">{insight.category}</td>
                  <td className="px-4 py-2"><AlertSeverityBadge severity={insight.severity} /></td>
                  <td className="px-4 py-2"><ConfidenceBadge confidence={insight.confidence_level} /></td>
                  <td className="px-4 py-2"><InsightStatusBadge status={insight.status} /></td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">
                    {[insight.field_name, insight.well_code, insight.equipment_tag].filter(Boolean).join(" / ") || "—"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {data && data.total > 0 ? (
        <div className="flex items-center justify-between text-sm text-zinc-500 dark:text-zinc-400">
          <span>{data.total} insight{data.total === 1 ? "" : "s"} — page {data.page} of {totalPages}</span>
          <div className="flex gap-2">
            <button type="button" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1} className="rounded-md border border-zinc-300 px-3 py-1 disabled:opacity-40 dark:border-zinc-700">Previous</button>
            <button type="button" onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages} className="rounded-md border border-zinc-300 px-3 py-1 disabled:opacity-40 dark:border-zinc-700">Next</button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
