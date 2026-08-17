"use client";

import { useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { TrendChart, type TrendSeries } from "@/components/charts/TrendChart";
import { BaselineSelector } from "@/components/what-if/BaselineSelector";
import { AssumptionForm } from "@/components/what-if/AssumptionForm";
import {
  ApiError,
  runSensitivity,
  SCENARIO_ASSUMPTION_FIELDS,
  type BaselineConfig,
  type ScenarioAssumptions,
  type SensitivityResponse,
} from "@/lib/api";
import { formatLabel } from "@/lib/format";

function isoDaysAgo(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

const CHART_COLORS = ["var(--chart-series-1)", "var(--chart-series-2)", "var(--chart-series-3)", "var(--chart-series-4)"];

export default function SensitivityAnalysisPage() {
  const [baseline, setBaseline] = useState<BaselineConfig>({ date_from: isoDaysAgo(30), date_to: isoDaysAgo(0) });
  const [baseAssumptions, setBaseAssumptions] = useState<ScenarioAssumptions>({});
  const [variable, setVariable] = useState<keyof ScenarioAssumptions>("downtime_change_pct");
  const [valuesText, setValuesText] = useState("0, -10, -20, -30, -40, -50");
  const [response, setResponse] = useState<SensitivityResponse | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleRun() {
    const values = valuesText
      .split(",")
      .map((v) => Number(v.trim()))
      .filter((v) => !Number.isNaN(v));

    if (values.length === 0) {
      setError("Enter at least one value to sweep, e.g. 0, -10, -20, -30.");
      return;
    }

    setIsRunning(true);
    setError(null);
    setResponse(null);
    try {
      const result = await runSensitivity(baseline, baseAssumptions, variable, values);
      setResponse(result);
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 422
          ? "Unable to sweep this variable — check the variable name and values."
          : "Unable to run sensitivity analysis. Check the baseline and try again.",
      );
    } finally {
      setIsRunning(false);
    }
  }

  const currencies = new Set<string>();
  for (const point of response?.points ?? []) {
    point.revenue_impact.forEach((m) => currencies.add(m.currency));
    point.margin_impact.forEach((m) => currencies.add(m.currency));
  }

  const chartData = (response?.points ?? []).map((point) => {
    const row: Record<string, number | string | null> = {
      variable_value: point.variable_value,
      recovered_production_bbl: point.recovered_production_bbl,
      recovered_downtime_hours: point.recovered_downtime_hours,
    };
    for (const currency of currencies) {
      row[`revenue_impact_${currency}`] = point.revenue_impact.find((m) => m.currency === currency)?.amount ?? null;
      row[`margin_impact_${currency}`] = point.margin_impact.find((m) => m.currency === currency)?.amount ?? null;
    }
    return row;
  });

  const productionSeries: TrendSeries[] = [
    { key: "recovered_production_bbl", label: "Est. Recovered Production", unit: "bbl", color: CHART_COLORS[0] },
  ];
  const impactSeries: TrendSeries[] = Array.from(currencies).flatMap((currency, index) => [
    { key: `revenue_impact_${currency}`, label: `Revenue Impact (${currency})`, unit: currency, color: CHART_COLORS[(index * 2) % CHART_COLORS.length] },
    { key: `margin_impact_${currency}`, label: `Margin Impact (${currency})`, unit: currency, color: CHART_COLORS[(index * 2 + 1) % CHART_COLORS.length] },
  ]);

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title="Sensitivity Analysis"
        description="Sweep one assumption across a range of values to see the estimated impact on recovered production, revenue, and margin. A basic sensitivity sweep, not a statistical model."
      />

      <section className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
        <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-50">Baseline Period &amp; Scope</h3>
        <BaselineSelector value={baseline} onChange={setBaseline} disabled={isRunning} />
      </section>

      <section className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
        <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-50">Variable to Sweep</h3>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
            Variable
            <select
              value={variable}
              onChange={(e) => setVariable(e.target.value as keyof ScenarioAssumptions)}
              disabled={isRunning}
              className="mt-1 block w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
            >
              {SCENARIO_ASSUMPTION_FIELDS.map((field) => (
                <option key={field} value={field}>
                  {formatLabel(field)}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
            Values to Sweep (comma-separated)
            <input
              value={valuesText}
              onChange={(e) => setValuesText(e.target.value)}
              disabled={isRunning}
              className="mt-1 block w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
            />
          </label>
        </div>
      </section>

      <section className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
        <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-50">
          Other Assumptions Held Constant (optional)
        </h3>
        <AssumptionForm values={baseAssumptions} onChange={setBaseAssumptions} disabled={isRunning} />
      </section>

      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

      <div>
        <button
          type="button"
          onClick={handleRun}
          disabled={isRunning}
          className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
        >
          {isRunning ? "Running…" : "Run Sensitivity Sweep"}
        </button>
      </div>

      {response ? (
        !response.baseline.data_sufficient ? (
          <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
            Insufficient historical data to calculate this scenario reliably. {response.baseline.missing_data_note}
          </div>
        ) : (
          <>
            <TrendChart title="Estimated Production Recovery" data={chartData} xKey="variable_value" series={productionSeries} showTableToggle />
            {impactSeries.length > 0 ? (
              <TrendChart title="Estimated Revenue &amp; Margin Impact" data={chartData} xKey="variable_value" series={impactSeries} showTableToggle />
            ) : null}
            <p className="text-xs text-zinc-400 dark:text-zinc-500">{response.disclaimer_text}</p>
          </>
        )
      ) : null}
    </div>
  );
}
