"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { PageHeader } from "@/components/layout/PageHeader";
import { AssumptionForm } from "@/components/what-if/AssumptionForm";
import { BaselineSelector } from "@/components/what-if/BaselineSelector";
import { ComparisonTable } from "@/components/what-if/ComparisonTable";
import { GuardrailBanner } from "@/components/what-if/GuardrailBanner";
import { MoneyStat } from "@/components/what-if/MoneyStat";
import { ScenarioComparisonCharts } from "@/components/what-if/ScenarioComparisonCharts";
import {
  ApiError,
  createScenario,
  previewScenario,
  type BaselineConfig,
  type ScenarioAssumptions,
  type ScenarioResults,
} from "@/lib/api";

function isoDaysAgo(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

function friendlyError(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    if (err.status === 422) {
      return "One or more assumptions are mathematically invalid (e.g. below -100%, a loss reduction above 100%, or a non-positive price). Adjust the values and try again.";
    }
    if (err.status === 404) {
      return "One of the selected scope items (field/facility/well/equipment) could not be found.";
    }
    if (err.message) return err.message;
  }
  return fallback;
}

export default function WhatIfBuilderPage() {
  const router = useRouter();
  const [baseline, setBaseline] = useState<BaselineConfig>({ date_from: isoDaysAgo(30), date_to: isoDaysAgo(0) });
  const [assumptions, setAssumptions] = useState<ScenarioAssumptions>({});
  const [results, setResults] = useState<ScenarioResults | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  async function handleRun() {
    setIsRunning(true);
    setRunError(null);
    setResults(null);
    try {
      const response = await previewScenario(baseline, assumptions);
      setResults(response.results);
    } catch (err) {
      setRunError(friendlyError(err, "Unable to run this scenario. Check the baseline and assumptions and try again."));
    } finally {
      setIsRunning(false);
    }
  }

  async function handleSave() {
    if (!name.trim()) {
      setSaveError("Name is required to save a scenario.");
      return;
    }
    setIsSaving(true);
    setSaveError(null);
    try {
      const scenario = await createScenario({
        name: name.trim(),
        description: description.trim() || null,
        baseline,
        assumptions,
      });
      router.push(`/what-if-simulator/scenarios/${scenario.id}`);
    } catch (err) {
      setSaveError(friendlyError(err, "Unable to save this scenario."));
    } finally {
      setIsSaving(false);
    }
  }

  const hasHardError = (results?.guardrail_flags ?? []).some((f) => f.severity === "error");

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title="Scenario Builder"
        description="Select a baseline period and scope, enter assumptions, then run the simulation. Nothing is saved, and no operational data is changed, until you choose to save a scenario."
      />

      <section className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
        <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-50">1. Baseline Period &amp; Scope</h3>
        <BaselineSelector value={baseline} onChange={setBaseline} disabled={isRunning || isSaving} />
      </section>

      <section className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
        <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-50">2. Scenario Assumptions</h3>
        <AssumptionForm values={assumptions} onChange={setAssumptions} disabled={isRunning || isSaving} />
      </section>

      {runError ? <p className="text-sm text-red-600 dark:text-red-400">{runError}</p> : null}

      <div>
        <button
          type="button"
          onClick={handleRun}
          disabled={isRunning}
          className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
        >
          {isRunning ? "Running…" : "Run Simulation"}
        </button>
      </div>

      {results ? (
        <>
          <GuardrailBanner flags={results.guardrail_flags} />

          {!results.baseline.data_sufficient ? (
            <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
              Insufficient historical data to calculate this scenario reliably. {results.baseline.missing_data_note}
            </div>
          ) : (
            <>
              <section>
                <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-50">3. Results</h3>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <KpiCard label="Baseline Oil Production" value={results.baseline.oil_bbl.toLocaleString()} unit="bbl" />
                  <KpiCard label="Scenario Oil Production" value={results.scenario.oil_bbl.toLocaleString()} unit="bbl" calculated />
                  <KpiCard
                    label="Est. Production Recovery (Downtime)"
                    value={results.scenario.recovered_production_bbl.toLocaleString()}
                    unit="bbl"
                    hint="Estimate — reported separately, not guaranteed"
                    calculated
                  />
                  <KpiCard
                    label="Est. Production Recovery (Loss Reduction)"
                    value={results.scenario.potential_loss_reduction_oil_bbl.toLocaleString()}
                    unit="bbl"
                    hint="Estimate — reported separately, not guaranteed"
                    calculated
                  />
                  <MoneyStat label="Baseline Revenue" amounts={results.baseline.revenue} />
                  <MoneyStat label="Scenario Revenue" amounts={results.scenario.revenue} />
                  <MoneyStat
                    label="Baseline Operating Margin"
                    amounts={results.baseline.margin}
                    hint={results.baseline.margin_currency_mismatch ? "Currency mismatch — see comparison table" : undefined}
                  />
                  <MoneyStat
                    label="Scenario Operating Margin"
                    amounts={results.scenario.margin}
                    hint={results.scenario.margin_currency_mismatch ? "Currency mismatch — see comparison table" : undefined}
                  />
                </div>
              </section>

              <section>
                <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-50">4. Baseline vs. Scenario</h3>
                <ScenarioComparisonCharts rows={results.comparison} />
                <div className="mt-4">
                  <ComparisonTable rows={results.comparison} />
                </div>
              </section>
            </>
          )}

          <section className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
            <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-50">5. Save This Scenario</h3>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
              <label className="block flex-1 text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Name
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Downtime reduction 20%"
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
                disabled={isSaving || hasHardError}
                className="shrink-0 rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
              >
                {isSaving ? "Saving…" : "Save Scenario"}
              </button>
            </div>
            {saveError ? <p className="mt-2 text-sm text-red-600 dark:text-red-400">{saveError}</p> : null}
          </section>
        </>
      ) : null}

      <p className="text-xs text-zinc-400 dark:text-zinc-500">
        <Link href="/what-if-simulator/scenarios" className="underline-offset-2 hover:underline">
          View saved scenarios
        </Link>
      </p>
    </div>
  );
}
