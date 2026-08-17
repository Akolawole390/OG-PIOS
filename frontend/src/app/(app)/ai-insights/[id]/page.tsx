"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { AlertSeverityBadge } from "@/components/alerts/AlertSeverityBadge";
import { ConfidenceBadge } from "@/components/ai-insights/ConfidenceBadge";
import { InsightStatusBadge } from "@/components/ai-insights/InsightStatusBadge";
import { EvidenceList } from "@/components/ai-insights/EvidenceList";
import { FeedbackButtons } from "@/components/ai-insights/FeedbackButtons";
import {
  getCurrentUser,
  getInsight,
  interpretInsight,
  updateInsightStatus,
  type CurrentUser,
  type InsightEntry,
} from "@/lib/api";

const CAN_ACT = new Set([
  "Administrator",
  "Production Operator",
  "Production Engineer",
  "Maintenance Engineer",
  "Management",
  "Analyst",
]);

function InfoItem({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">{label}</p>
      <p className="mt-1 text-sm text-zinc-900 dark:text-zinc-50">{value ?? "—"}</p>
    </div>
  );
}

export default function InsightDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);

  const [insight, setInsight] = useState<InsightEntry | null>(null);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function load() {
    getInsight(id).then(setInsight).catch(() => setError("Unable to load this insight."));
  }

  useEffect(() => {
    load();
    getCurrentUser().then(setCurrentUser).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const canAct = currentUser ? CAN_ACT.has(currentUser.role_name) : false;

  async function handleStatus(status: "reviewed" | "dismissed") {
    setIsSubmitting(true);
    setError(null);
    try {
      await updateInsightStatus(id, status);
      load();
    } catch {
      setError("Unable to update this insight. Try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleInterpret() {
    setIsSubmitting(true);
    setError(null);
    try {
      await interpretInsight(id);
      load();
    } catch {
      setError("Unable to generate an AI interpretation. Try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (!insight) {
    return (
      <div className="flex flex-1 flex-col gap-6">
        <PageHeader title="Insight" description="Loading…" />
        {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}
      </div>
    );
  }

  const hasRelatedRecords =
    insight.well_id || insight.equipment_id || insight.maintenance_record_id || insight.production_loss_id || insight.alert_id || insight.category === "economics";

  return (
    <div className="flex flex-1 flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <PageHeader title={insight.title} description={`${insight.category} · ${insight.insight_type}`} />
        <div className="flex shrink-0 items-center gap-2">
          <AlertSeverityBadge severity={insight.severity} />
          <ConfidenceBadge confidence={insight.confidence_level} />
          <InsightStatusBadge status={insight.status} />
        </div>
      </div>

      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

      <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Summary</h3>
        <p className="mt-2 text-sm text-zinc-700 dark:text-zinc-300">{insight.summary}</p>
        {insight.data_quality_note ? (
          <p className="mt-3 rounded-md border border-amber-300 bg-amber-50 p-2 text-xs text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
            Data quality: {insight.data_quality_note}
          </p>
        ) : null}
      </div>

      <div>
        <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-50">Evidence</h3>
        <EvidenceList evidence={insight.evidence} />
      </div>

      {(insight.estimated_production_impact_value !== null || insight.estimated_financial_impact_value !== null) ? (
        <div className="grid grid-cols-1 gap-4 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950 sm:grid-cols-2">
          <div>
            <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Potential Production Impact</h3>
            {insight.estimated_production_impact_value !== null ? (
              <>
                <p className="mt-1 text-lg font-semibold text-zinc-900 dark:text-zinc-50">
                  {insight.estimated_production_impact_value} {insight.estimated_production_impact_unit}
                </p>
                {insight.estimated_production_impact_note ? (
                  <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{insight.estimated_production_impact_note}</p>
                ) : null}
              </>
            ) : (
              <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">Not applicable to this insight.</p>
            )}
          </div>
          <div>
            <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Potential Financial Impact</h3>
            {insight.estimated_financial_impact_value !== null ? (
              <>
                <p className="mt-1 text-lg font-semibold text-zinc-900 dark:text-zinc-50">
                  {insight.estimated_financial_impact_currency} {insight.estimated_financial_impact_value.toLocaleString()}
                </p>
                {insight.estimated_financial_impact_note ? (
                  <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{insight.estimated_financial_impact_note}</p>
                ) : null}
              </>
            ) : (
              <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">Not applicable to this insight.</p>
            )}
          </div>
        </div>
      ) : null}

      {insight.recommended_investigation ? (
        <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Recommended Investigation</h3>
          <p className="mt-2 text-sm text-zinc-700 dark:text-zinc-300">{insight.recommended_investigation}</p>
        </div>
      ) : null}

      <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Related Records</h3>
        <div className="mt-3 flex flex-wrap gap-4 text-sm">
          {insight.field_name ? <span>Field: {insight.field_name}</span> : null}
          {insight.facility_name ? <span>Facility: {insight.facility_name}</span> : null}
          {insight.well_id ? (
            <Link href={`/wells/${insight.well_code}`} className="text-zinc-900 hover:underline dark:text-zinc-50">
              Well: {insight.well_code}
            </Link>
          ) : null}
          {insight.equipment_id ? (
            <Link href={`/equipment/${insight.equipment_id}`} className="text-zinc-900 hover:underline dark:text-zinc-50">
              Equipment: {insight.equipment_tag}
            </Link>
          ) : null}
          {insight.maintenance_record_id ? (
            <Link href={`/maintenance/${insight.maintenance_record_id}`} className="text-zinc-900 hover:underline dark:text-zinc-50">
              Maintenance: {insight.maintenance_work_order_number ?? insight.maintenance_record_id}
            </Link>
          ) : null}
          {insight.production_loss_id ? (
            <Link href={`/production-loss/${insight.production_loss_id}`} className="text-zinc-900 hover:underline dark:text-zinc-50">
              Production Loss Event #{insight.production_loss_id}
            </Link>
          ) : null}
          {insight.alert_id ? (
            <Link href={`/alerts/${insight.alert_id}`} className="text-zinc-900 hover:underline dark:text-zinc-50">
              Related Alert #{insight.alert_id}
            </Link>
          ) : null}
          {insight.category === "economics" ? (
            <Link href="/cost-revenue" className="text-zinc-900 hover:underline dark:text-zinc-50">
              Cost & Revenue Dashboard
            </Link>
          ) : null}
          {!hasRelatedRecords ? <span className="text-zinc-500 dark:text-zinc-400">No linked records.</span> : null}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950 sm:grid-cols-4">
        <InfoItem label="Occurrences" value={String(insight.occurrence_count)} />
        <InfoItem label="Generated" value={insight.generated_at.slice(0, 19).replace("T", " ")} />
        <InfoItem label="Last Confirmed" value={insight.last_confirmed_at.slice(0, 19).replace("T", " ")} />
        <InfoItem label="Stale?" value={insight.is_stale ? `Yes — ${insight.days_since_confirmed} day(s) since last confirmed` : "No"} />
      </div>

      {canAct ? (
        <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Actions</h3>
          <div className="mt-3 flex flex-wrap gap-2">
            <button type="button" disabled={isSubmitting} onClick={() => handleStatus("reviewed")} className="rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300">
              Mark Reviewed
            </button>
            <button type="button" disabled={isSubmitting} onClick={() => handleStatus("dismissed")} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-900">
              Dismiss
            </button>
            <button type="button" disabled={isSubmitting} onClick={handleInterpret} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-900">
              {insight.ai_interpretation ? "Regenerate AI Interpretation" : "Add AI Interpretation"}
            </button>
          </div>
        </div>
      ) : null}

      {insight.ai_interpretation ? (
        <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">
            AI Interpretation {insight.ai_provider ? `(${insight.ai_provider}${insight.ai_model ? ` / ${insight.ai_model}` : ""})` : ""}
          </h3>
          <p className="mt-2 whitespace-pre-wrap text-sm text-zinc-700 dark:text-zinc-300">{insight.ai_interpretation}</p>
        </div>
      ) : null}

      {canAct ? (
        <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-50">Feedback</h3>
          <FeedbackButtons
            insightId={insight.id}
            existing={insight.feedback}
            onSubmitted={(feedback) => setInsight({ ...insight, feedback })}
          />
        </div>
      ) : null}

      <p className="text-xs text-zinc-400 dark:text-zinc-500">{insight.disclaimer_text}</p>
    </div>
  );
}
