"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { ReportFilterForm } from "@/components/reports/ReportFilterForm";
import { ReportSectionToggles } from "@/components/reports/ReportSectionToggles";
import { ReportViewer } from "@/components/reports/ReportViewer";
import {
  ApiError,
  createReport,
  getReportTypes,
  listScenarios,
  previewReport,
  type PreviewReportResponse,
  type ReportFilters,
  type ReportType,
  type ReportTypeInfo,
  type ScenarioListItem,
} from "@/lib/api";

function isoDaysAgo(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

function defaultFiltersFor(type: ReportType): ReportFilters {
  const today = isoDaysAgo(0);
  switch (type) {
    case "daily_operations":
      return { date_from: today, date_to: today };
    case "weekly_production":
      return { date_from: isoDaysAgo(6), date_to: today };
    case "monthly_management":
      return { date_from: isoDaysAgo(29), date_to: today };
    case "what_if_scenario":
      return {};
  }
}

function friendlyError(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    if (err.status === 422) return "Check the date range and try again.";
    if (err.status === 404) return "One of the selected filters (field/facility/well/equipment/scenario) could not be found.";
    if (err.message) return err.message;
  }
  return fallback;
}

export default function ReportBuilderPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialType = (searchParams.get("type") as ReportType | null) ?? "daily_operations";

  const [types, setTypes] = useState<ReportTypeInfo[]>([]);
  const [reportType, setReportType] = useState<ReportType>(initialType);
  const [filters, setFilters] = useState<ReportFilters>(defaultFiltersFor(initialType));
  const [sections, setSections] = useState<string[]>([]);
  const [narrative, setNarrative] = useState(false);
  const [scenarios, setScenarios] = useState<ScenarioListItem[]>([]);

  const [preview, setPreview] = useState<PreviewReportResponse | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    getReportTypes().then((res) => setTypes(res.types)).catch(() => undefined);
    listScenarios({ page_size: 100, sort: "created_at", order: "desc" }).then((res) => setScenarios(res.items)).catch(() => undefined);
  }, []);

  const currentTypeInfo = types.find((t) => t.id === reportType);
  const availableSections = currentTypeInfo?.sections ?? [];

  function handleTypeChange(next: ReportType) {
    setReportType(next);
    setFilters(defaultFiltersFor(next));
    setSections([]);
    setPreview(null);
  }

  async function handleRun() {
    setIsRunning(true);
    setRunError(null);
    setPreview(null);
    try {
      const response = await previewReport({ report_type: reportType, filters, sections: sections.length ? sections : undefined, narrative });
      setPreview(response);
    } catch (err) {
      setRunError(friendlyError(err, "Unable to generate this report. Check the filters and try again."));
    } finally {
      setIsRunning(false);
    }
  }

  async function handleSave() {
    if (!name.trim()) {
      setSaveError("Name is required to save a report.");
      return;
    }
    setIsSaving(true);
    setSaveError(null);
    try {
      const report = await createReport({
        report_type: reportType,
        name: name.trim(),
        description: description.trim() || null,
        filters,
        sections: sections.length ? sections : undefined,
        narrative,
      });
      router.push(`/reports/saved/${report.id}`);
    } catch (err) {
      setSaveError(friendlyError(err, "Unable to save this report."));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title="Report Builder"
        description="Select a report type, filters, and sections, preview the result, then save it. Nothing is saved until you choose to save it."
      />

      <section className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
        <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-50">1. Report Type</h3>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {types.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => handleTypeChange(t.id)}
              disabled={isRunning || isSaving}
              className={`rounded-md border px-3 py-2 text-left text-sm font-medium transition-colors disabled:opacity-50 ${
                reportType === t.id
                  ? "border-zinc-900 bg-zinc-900 text-white dark:border-zinc-100 dark:bg-zinc-100 dark:text-zinc-900"
                  : "border-zinc-300 text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </section>

      <section className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
        <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-50">2. Date Range &amp; Assets</h3>
        {reportType === "what_if_scenario" ? (
          <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
            Saved Scenario
            <select
              disabled={isRunning || isSaving}
              value={filters.scenario_id ?? ""}
              onChange={(e) => setFilters({ ...filters, scenario_id: e.target.value ? Number(e.target.value) : undefined })}
              className="mt-1 block w-full max-w-md rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
            >
              <option value="">Select a scenario…</option>
              {scenarios.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </label>
        ) : (
          <ReportFilterForm value={filters} onChange={setFilters} disabled={isRunning || isSaving} />
        )}
      </section>

      {availableSections.length > 0 ? (
        <section className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-50">3. Sections</h3>
          <ReportSectionToggles
            available={availableSections}
            selected={sections.length ? sections : availableSections}
            onChange={setSections}
            disabled={isRunning || isSaving}
          />
        </section>
      ) : null}

      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={handleRun}
          disabled={isRunning || (reportType === "what_if_scenario" && !filters.scenario_id)}
          className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
        >
          {isRunning ? "Generating…" : "4. Preview Report"}
        </button>
        {reportType === "monthly_management" ? (
          <label className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400">
            <input type="checkbox" checked={narrative} onChange={(e) => setNarrative(e.target.checked)} disabled={isRunning} />
            Include AI narrative summary
          </label>
        ) : null}
      </div>

      {runError ? <p className="text-sm text-red-600 dark:text-red-400">{runError}</p> : null}

      {preview ? (
        <>
          <section>
            <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-50">5. Preview</h3>
            <ReportViewer results={preview.results} />
          </section>

          <section className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
            <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-50">6. Save This Report</h3>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
              <label className="block flex-1 text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Name
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Daily Operations - Niger Delta Field"
                  className="mt-1 block w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                />
              </label>
              <label className="block flex-1 text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Description (optional)
                <input
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="mt-1 block w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                />
              </label>
              <button
                type="button"
                onClick={handleSave}
                disabled={isSaving}
                className="shrink-0 rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
              >
                {isSaving ? "Saving…" : "Save Report"}
              </button>
            </div>
            {saveError ? <p className="mt-2 text-sm text-red-600 dark:text-red-400">{saveError}</p> : null}
          </section>
        </>
      ) : null}
    </div>
  );
}
