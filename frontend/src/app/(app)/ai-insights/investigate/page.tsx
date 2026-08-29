"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { ConfidenceBadge } from "@/components/ai-insights/ConfidenceBadge";
import { ApiError, investigateEvent, type InvestigationResult, type PossibleCause } from "@/lib/api";

const CAUSE_GROUPS: { type: PossibleCause["evidence_type"]; label: string; style: string }[] = [
  { type: "observed_fact", label: "Observed Facts", style: "border-blue-300 bg-blue-50 dark:border-blue-800 dark:bg-blue-950/30" },
  { type: "calculated_metric", label: "Calculated Metrics", style: "border-purple-300 bg-purple-50 dark:border-purple-800 dark:bg-purple-950/30" },
  { type: "correlation", label: "Correlations", style: "border-amber-300 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30" },
  { type: "possible_contributor", label: "Possible Contributors", style: "border-orange-300 bg-orange-50 dark:border-orange-800 dark:bg-orange-950/30" },
];

function PossibleCausesList({ causes }: { causes: PossibleCause[] }) {
  return (
    <div className="flex flex-col gap-3">
      {CAUSE_GROUPS.map((group) => {
        const items = causes.filter((c) => c.evidence_type === group.type);
        if (items.length === 0) return null;
        return (
          <div key={group.type} className={`rounded-lg border p-4 ${group.style}`}>
            <h4 className="mb-2 text-sm font-semibold text-zinc-900 dark:text-zinc-50">{group.label}</h4>
            <ul className="space-y-1.5 text-sm text-zinc-700 dark:text-zinc-300">
              {items.map((item, i) => (
                <li key={i}>{item.description}</li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}

function InvestigateForm() {
  const searchParams = useSearchParams();
  const [insightId, setInsightId] = useState(searchParams.get("insight_id") ?? "");
  const [wellId, setWellId] = useState(searchParams.get("well_id") ?? "");
  const [equipmentId, setEquipmentId] = useState(searchParams.get("equipment_id") ?? "");
  const [result, setResult] = useState<InvestigationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  async function runInvestigation() {
    if (!insightId.trim() && !wellId.trim() && !equipmentId.trim()) {
      setError("Enter an Insight ID, Well ID, or Equipment ID to investigate.");
      return;
    }
    setError(null);
    setIsLoading(true);
    try {
      const target: { insight_id?: number; well_id?: number; equipment_id?: number } = {};
      if (insightId.trim()) target.insight_id = Number(insightId);
      if (wellId.trim()) target.well_id = Number(wellId);
      if (equipmentId.trim()) target.equipment_id = Number(equipmentId);
      setResult(await investigateEvent(target));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to investigate this event. It may be rate-limited — wait a minute and try again.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    if (searchParams.get("insight_id")) {
      runInvestigation();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title="Investigate Event"
        description="Root-cause analysis over real recorded data — evidence, possible causes, and an AI assessment where configured. Not a guaranteed conclusion."
      />

      <div className="flex flex-wrap items-end gap-3 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
        <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
          Insight ID
          <input
            type="number"
            value={insightId}
            onChange={(e) => setInsightId(e.target.value)}
            className="mt-1 block w-32 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          />
        </label>
        <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
          Well ID
          <input
            type="number"
            value={wellId}
            onChange={(e) => setWellId(e.target.value)}
            className="mt-1 block w-32 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          />
        </label>
        <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
          Equipment ID
          <input
            type="number"
            value={equipmentId}
            onChange={(e) => setEquipmentId(e.target.value)}
            className="mt-1 block w-32 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          />
        </label>
        <button
          type="button"
          onClick={runInvestigation}
          disabled={isLoading}
          className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
        >
          {isLoading ? "Investigating…" : "Investigate"}
        </button>
      </div>

      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

      {result ? (
        <div className="flex flex-col gap-5 rounded-lg border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">{result.event}</h2>
            <ConfidenceBadge confidence={result.confidence_level} />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">Impact</p>
              <p className="mt-1 text-sm text-zinc-800 dark:text-zinc-200">{result.impact_summary}</p>
            </div>
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">Primary Contributor</p>
              <p className="mt-1 text-sm text-zinc-800 dark:text-zinc-200">{result.primary_contributor ?? "Not identified"}</p>
            </div>
          </div>

          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">Possible Causes</p>
            <PossibleCausesList causes={result.possible_causes} />
          </div>

          <div>
            <div className="mb-2 flex items-center gap-2">
              <p className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">AI Assessment</p>
              <span className="rounded border border-zinc-300 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-zinc-500 dark:border-zinc-700 dark:text-zinc-400">
                {result.answered_by === "deterministic" ? "From OG-PIOS data" : "AI-interpreted"}
              </span>
            </div>
            <p className="whitespace-pre-wrap text-sm text-zinc-800 dark:text-zinc-200">{result.ai_assessment}</p>
          </div>

          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">Recommended Investigation</p>
            <p className="mt-1 text-sm text-zinc-800 dark:text-zinc-200">{result.recommended_investigation}</p>
          </div>

          {result.sources.length > 0 ? (
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              Sources: {result.sources.map((s) => s.source_label).join(", ")}
            </p>
          ) : null}

          <p className="border-t border-zinc-200 pt-3 text-xs text-zinc-400 dark:border-zinc-800 dark:text-zinc-500">
            {result.disclaimer_text}
          </p>
        </div>
      ) : null}
    </div>
  );
}

export default function InvestigateEventPage() {
  return (
    <Suspense fallback={null}>
      <InvestigateForm />
    </Suspense>
  );
}
