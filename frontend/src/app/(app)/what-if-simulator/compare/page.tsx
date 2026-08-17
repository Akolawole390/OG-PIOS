"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { BarChart, type BarDatum } from "@/components/charts/BarChart";
import { PageHeader } from "@/components/layout/PageHeader";
import { ComparisonTable } from "@/components/what-if/ComparisonTable";
import { MoneyStat } from "@/components/what-if/MoneyStat";
import {
  compareScenarios,
  listScenarios,
  type CompareResponse,
  type ScenarioCompareEntry,
  type ScenarioListItem,
} from "@/lib/api";

function oilProductionBars(scenarios: ScenarioCompareEntry[]): BarDatum[] {
  return scenarios
    .filter((entry) => entry.results)
    .map((entry) => ({ key: String(entry.id), label: entry.name, value: entry.results!.scenario.oil_bbl }));
}

/** Builds one BarDatum[] per currency present across the selected scenarios for a given money
 * field — money can never be blended across currencies, so each currency gets its own chart
 * rather than one chart mixing e.g. USD and NGN bars. */
function moneyBarsByCurrency(
  scenarios: ScenarioCompareEntry[],
  field: "revenue" | "margin",
): Record<string, BarDatum[]> {
  const byCurrency: Record<string, BarDatum[]> = {};
  for (const entry of scenarios) {
    if (!entry.results) continue;
    for (const money of entry.results.scenario[field]) {
      byCurrency[money.currency] ??= [];
      byCurrency[money.currency].push({ key: String(entry.id), label: entry.name, value: money.amount });
    }
  }
  return byCurrency;
}

export default function CompareScenariosPage() {
  const searchParams = useSearchParams();
  const initialIds = (searchParams.get("ids") ?? "")
    .split(",")
    .map((v) => Number(v))
    .filter((v) => Number.isFinite(v) && v > 0);

  const [available, setAvailable] = useState<ScenarioListItem[]>([]);
  const [selected, setSelected] = useState<number[]>(initialIds);
  const [narrative, setNarrative] = useState(false);
  const [result, setResult] = useState<CompareResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const oilBars = useMemo(() => (result ? oilProductionBars(result.scenarios) : []), [result]);
  const revenueBarsByCurrency = useMemo(
    () => (result ? moneyBarsByCurrency(result.scenarios, "revenue") : {}),
    [result],
  );
  const marginBarsByCurrency = useMemo(
    () => (result ? moneyBarsByCurrency(result.scenarios, "margin") : {}),
    [result],
  );

  useEffect(() => {
    listScenarios({ page_size: 100, sort: "created_at", order: "desc" })
      .then((res) => setAvailable(res.items))
      .catch(() => undefined);
  }, []);

  function toggle(id: number) {
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }

  async function handleCompare() {
    if (selected.length < 2) {
      setError("Select at least 2 scenarios to compare.");
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const response = await compareScenarios(selected, narrative);
      setResult(response);
    } catch {
      setError("Unable to compare these scenarios. They may need to be run first.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title="Compare Scenarios"
        description="Compares each scenario's saved results — never recomputed here. Rerun a scenario first if you want it compared against current data."
      />

      <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
        <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-50">Select Scenarios</h3>
        <div className="flex max-h-56 flex-col gap-1 overflow-y-auto">
          {available.map((item) => (
            <label key={item.id} className="flex items-center gap-2 rounded px-2 py-1 text-sm hover:bg-zinc-50 dark:hover:bg-zinc-900">
              <input type="checkbox" checked={selected.includes(item.id)} onChange={() => toggle(item.id)} />
              <span className="font-medium text-zinc-900 dark:text-zinc-50">{item.name}</span>
              <span className="text-xs text-zinc-500 dark:text-zinc-400">
                {item.baseline_date_from} to {item.baseline_date_to}
              </span>
            </label>
          ))}
          {available.length === 0 ? <p className="text-sm text-zinc-500 dark:text-zinc-400">No saved scenarios yet.</p> : null}
        </div>
        <div className="mt-4 flex items-center gap-3">
          <button
            type="button"
            onClick={handleCompare}
            disabled={isLoading || selected.length < 2}
            className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
          >
            {isLoading ? "Comparing…" : `Compare ${selected.length} Selected`}
          </button>
          <label className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400">
            <input type="checkbox" checked={narrative} onChange={(e) => setNarrative(e.target.checked)} />
            Include AI narrative summary
          </label>
        </div>
        {error ? <p className="mt-2 text-sm text-red-600 dark:text-red-400">{error}</p> : null}
      </div>

      {result ? (
        <>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {result.scenarios.map((entry) => (
              <div key={entry.id} className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
                <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">{entry.name}</h3>
                {!entry.results ? (
                  <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">Not run yet.</p>
                ) : (
                  <div className="mt-3 grid grid-cols-2 gap-3">
                    <MoneyStat label="Scenario Revenue" amounts={entry.results.scenario.revenue} />
                    <MoneyStat label="Scenario Margin" amounts={entry.results.scenario.margin} />
                  </div>
                )}
              </div>
            ))}
          </div>

          {oilBars.length > 0 ? (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <BarChart title="Scenario Oil Production (bbl)" data={oilBars} unit="bbl" />
              {Object.entries(revenueBarsByCurrency).map(([currency, bars]) => (
                <BarChart key={`revenue-${currency}`} title={`Scenario Revenue (${currency})`} data={bars} unit={currency} />
              ))}
              {Object.entries(marginBarsByCurrency).map(([currency, bars]) => (
                <BarChart key={`margin-${currency}`} title={`Scenario Margin (${currency})`} data={bars} unit={currency} />
              ))}
            </div>
          ) : null}

          {result.ai_narrative ? (
            <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
              <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">AI Narrative Summary</h3>
              <p className="mt-2 whitespace-pre-wrap text-sm text-zinc-700 dark:text-zinc-300">{result.ai_narrative}</p>
            </div>
          ) : null}

          {result.scenarios.map((entry) =>
            entry.results ? (
              <section key={entry.id}>
                <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-50">{entry.name}: Baseline vs. Scenario</h3>
                <ComparisonTable rows={entry.results.comparison} />
              </section>
            ) : null,
          )}

          <p className="text-xs text-zinc-400 dark:text-zinc-500">{result.disclaimer_text}</p>
        </>
      ) : null}
    </div>
  );
}
