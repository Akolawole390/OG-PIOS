"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { PageHeader } from "@/components/layout/PageHeader";
import { MoneyStat } from "@/components/what-if/MoneyStat";
import { ScenarioComparisonCharts } from "@/components/what-if/ScenarioComparisonCharts";
import { getScenario, listScenarios, type Scenario, type ScenarioListItem } from "@/lib/api";

export default function WhatIfSimulatorPage() {
  const [recent, setRecent] = useState<ScenarioListItem[]>([]);
  const [latest, setLatest] = useState<Scenario | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    listScenarios({ sort: "last_run_at", order: "desc", page_size: 5 })
      .then((res) => {
        setRecent(res.items);
        const mostRecent = res.items.find((item) => item.has_results);
        return mostRecent ? getScenario(mostRecent.id).then(setLatest) : undefined;
      })
      .catch(() => undefined)
      .finally(() => setIsLoading(false));
  }, []);

  const results = latest?.results ?? null;

  return (
    <div className="flex flex-1 flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <PageHeader
          title="What-If Simulator"
          description="Compare a computed baseline against a hypothetical scenario. This is a planning tool — it never changes real production, cost, maintenance, or equipment records, and never controls equipment."
        />
        <div className="flex shrink-0 gap-2">
          <Link
            href="/what-if-simulator/builder"
            className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
          >
            New Scenario
          </Link>
          <Link
            href="/what-if-simulator/scenarios"
            className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900"
          >
            Saved Scenarios
          </Link>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 text-sm">
        <Link href="/what-if-simulator/compare" className="text-zinc-600 underline-offset-2 hover:underline dark:text-zinc-400">
          Compare Scenarios
        </Link>
        <span className="text-zinc-300 dark:text-zinc-700">·</span>
        <Link href="/what-if-simulator/sensitivity" className="text-zinc-600 underline-offset-2 hover:underline dark:text-zinc-400">
          Sensitivity Analysis
        </Link>
      </div>

      {!isLoading && recent.length === 0 ? (
        <div className="rounded-lg border border-dashed border-zinc-300 p-8 text-center dark:border-zinc-700">
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            No scenarios yet. Start in the Scenario Builder to compare a baseline against a hypothetical change —
            e.g. a downtime reduction or an operating cost change.
          </p>
          <Link
            href="/what-if-simulator/builder"
            className="mt-3 inline-block rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
          >
            Build a Scenario
          </Link>
        </div>
      ) : null}

      {latest && results && results.baseline.data_sufficient ? (
        <>
          <div>
            <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Most Recently Run: {latest.name}</h3>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              {results.baseline.period_start} to {results.baseline.period_end}
              {latest.field_name ? ` · ${latest.field_name}` : ""}
            </p>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCard label="Baseline Production" value={results.baseline.oil_bbl.toLocaleString()} unit="bbl" />
            <KpiCard label="Scenario Production" value={results.scenario.oil_bbl.toLocaleString()} unit="bbl" calculated />
            <KpiCard
              label="Est. Production Recovery"
              value={(results.scenario.recovered_production_bbl + results.scenario.potential_loss_reduction_oil_bbl).toLocaleString()}
              unit="bbl"
              hint="From downtime + production-loss reduction — estimate only"
              calculated
            />
            <KpiCard
              label="Margin Improvement"
              value={
                results.baseline.margin[0] && results.scenario.margin[0] && results.baseline.margin[0].currency === results.scenario.margin[0].currency
                  ? (results.scenario.margin[0].amount - results.baseline.margin[0].amount).toLocaleString(undefined, { maximumFractionDigits: 0 })
                  : "—"
              }
              unit={results.scenario.margin[0]?.currency ?? undefined}
              hint="Estimate — requires engineering/management review"
              calculated
            />
            <MoneyStat label="Baseline Revenue" amounts={results.baseline.revenue} />
            <MoneyStat label="Scenario Revenue" amounts={results.scenario.revenue} />
            <MoneyStat label="Baseline Operating Cost" amounts={results.baseline.total_cost} />
            <MoneyStat label="Scenario Operating Cost" amounts={results.scenario.total_cost} />
          </div>
          <ScenarioComparisonCharts rows={results.comparison} />
          <Link
            href={`/what-if-simulator/scenarios/${latest.id}`}
            className="w-fit text-sm font-medium text-zinc-900 underline-offset-2 hover:underline dark:text-zinc-50"
          >
            View full scenario →
          </Link>
        </>
      ) : null}

      {recent.length > 0 ? (
        <div>
          <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-50">Recent Scenarios</h3>
          <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-zinc-200 bg-zinc-50 text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
                  <th className="px-4 py-2 font-medium">Name</th>
                  <th className="px-4 py-2 font-medium">Baseline Period</th>
                  <th className="px-4 py-2 font-medium">Last Run</th>
                </tr>
              </thead>
              <tbody>
                {recent.map((item) => (
                  <tr key={item.id} className="border-b border-zinc-100 last:border-0 hover:bg-zinc-50 dark:border-zinc-900 dark:hover:bg-zinc-900">
                    <td className="px-4 py-2">
                      <Link href={`/what-if-simulator/scenarios/${item.id}`} className="font-medium text-zinc-900 hover:underline dark:text-zinc-50">
                        {item.name}
                      </Link>
                    </td>
                    <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">
                      {item.baseline_date_from} to {item.baseline_date_to}
                    </td>
                    <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">
                      {item.last_run_at ? item.last_run_at.slice(0, 19).replace("T", " ") : "Never"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </div>
  );
}
