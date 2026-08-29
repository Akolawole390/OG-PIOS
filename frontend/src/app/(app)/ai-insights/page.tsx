"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { PageHeader } from "@/components/layout/PageHeader";
import { BarChart, type BarDatum } from "@/components/charts/BarChart";
import { ConfidenceBadge } from "@/components/ai-insights/ConfidenceBadge";
import { InsightStatusBadge } from "@/components/ai-insights/InsightStatusBadge";
import {
  getCurrentUser,
  getInsightSummary,
  runInsightEngine,
  type CurrentUser,
  type InsightSummary,
} from "@/lib/api";

export default function AiInsightsPage() {
  const [summary, setSummary] = useState<InsightSummary | null>(null);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [runMessage, setRunMessage] = useState<string | null>(null);

  function load() {
    getInsightSummary().then(setSummary).catch(() => undefined);
  }

  useEffect(() => {
    load();
    getCurrentUser().then(setCurrentUser).catch(() => undefined);
  }, []);

  async function handleRun() {
    setIsRunning(true);
    setRunMessage(null);
    try {
      const result = await runInsightEngine();
      setRunMessage(`${result.created} created, ${result.updated} reaffirmed.`);
      load();
    } catch {
      setRunMessage("Unable to run the insight engine. Try again.");
    } finally {
      setIsRunning(false);
    }
  }

  const canRun = currentUser?.role_name === "Administrator";
  const categoryData: BarDatum[] = (summary?.by_category ?? []).map((c) => ({
    key: c.category, label: c.category, value: c.count,
  }));
  const confidenceData: BarDatum[] = Object.entries(summary?.by_confidence ?? {}).map(([key, value]) => ({
    key, label: key, value,
  }));

  return (
    <div className="flex flex-1 flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <PageHeader
          title="AI Insights"
          description="Evidence-based observations, possible contributors, and recommended investigations — analyzing existing OG-PIOS data, never inventing it."
        />
        <div className="flex shrink-0 items-center gap-2">
          <Link
            href="/ai-insights/assistant"
            className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
          >
            Ask Assistant
          </Link>
          <Link
            href="/ai-insights/investigate"
            className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
          >
            Investigate Event
          </Link>
          <Link
            href="/ai-insights/list"
            className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
          >
            View All Insights
          </Link>
          {canRun ? (
            <button
              type="button"
              onClick={handleRun}
              disabled={isRunning}
              className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
            >
              {isRunning ? "Running…" : "Run Engine"}
            </button>
          ) : null}
        </div>
      </div>

      {runMessage ? <p className="text-sm text-zinc-600 dark:text-zinc-400">{runMessage}</p> : null}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard label="Total Insights" value={String(summary?.total ?? "—")} />
        <KpiCard label="Open" value={String(summary?.open_count ?? "—")} />
        <KpiCard label="Critical" value={String(summary?.by_severity.critical ?? "—")} />
        <KpiCard label="High" value={String(summary?.by_severity.high ?? "—")} />
        <KpiCard label="Medium" value={String(summary?.by_severity.medium ?? "—")} />
        <KpiCard label="Low" value={String(summary?.by_severity.low ?? "—")} />
        <KpiCard label="Informational" value={String(summary?.by_severity.informational ?? "—")} />
        <KpiCard label="High Confidence" value={String(summary?.by_confidence.high ?? "—")} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <BarChart title="Insights by Category" data={categoryData} />
        <BarChart title="Insights by Confidence" data={confidenceData} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Critical Insights</h3>
          {summary && summary.critical.length > 0 ? (
            <ul className="mt-3 space-y-2 text-sm">
              {summary.critical.map((insight) => (
                <li key={insight.id} className="flex items-start justify-between gap-3 border-b border-zinc-100 pb-2 last:border-0 dark:border-zinc-900">
                  <div>
                    <Link href={`/ai-insights/${insight.id}`} className="font-medium text-zinc-900 hover:underline dark:text-zinc-50">
                      {insight.title}
                    </Link>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400">{insight.summary}</p>
                  </div>
                  <ConfidenceBadge confidence={insight.confidence_level} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-zinc-500 dark:text-zinc-400">No open critical insights.</p>
          )}
        </div>

        <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Recent Insights</h3>
          {summary && summary.recent.length > 0 ? (
            <ul className="mt-3 space-y-2 text-sm">
              {summary.recent.map((insight) => (
                <li key={insight.id} className="flex items-start justify-between gap-3 border-b border-zinc-100 pb-2 last:border-0 dark:border-zinc-900">
                  <div>
                    <Link href={`/ai-insights/${insight.id}`} className="font-medium text-zinc-900 hover:underline dark:text-zinc-50">
                      {insight.title}
                    </Link>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400">{insight.evidence.length} evidence item(s)</p>
                  </div>
                  <InsightStatusBadge status={insight.status} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-zinc-500 dark:text-zinc-400">No insights yet.</p>
          )}
        </div>
      </div>

      <div className="flex flex-wrap gap-3 text-sm">
        <Link href="/ai-insights/daily-brief" className="text-zinc-700 underline dark:text-zinc-300">
          Daily Operations Brief
        </Link>
        <span className="text-zinc-300 dark:text-zinc-700">·</span>
        <Link href="/ai-insights/management-summary" className="text-zinc-700 underline dark:text-zinc-300">
          Management Summary
        </Link>
      </div>

      {summary ? <p className="text-xs text-zinc-400 dark:text-zinc-500">{summary.disclaimer_text}</p> : null}
    </div>
  );
}
