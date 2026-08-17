"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { PageHeader } from "@/components/layout/PageHeader";
import { ComparisonTable } from "@/components/what-if/ComparisonTable";
import { GuardrailBanner } from "@/components/what-if/GuardrailBanner";
import { MoneyStat } from "@/components/what-if/MoneyStat";
import { ScenarioComparisonCharts } from "@/components/what-if/ScenarioComparisonCharts";
import {
  deleteScenario,
  getCurrentUser,
  getScenario,
  interpretScenario,
  rerunScenario,
  updateScenario,
  type CurrentUser,
  type Scenario,
  type ScenarioInterpretResponse,
} from "@/lib/api";

const CAN_ACT = new Set([
  "Administrator",
  "Production Operator",
  "Production Engineer",
  "Maintenance Engineer",
  "Management",
  "Analyst",
]);

export default function ScenarioDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = Number(params.id);

  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);

  const [isRenaming, setIsRenaming] = useState(false);
  const [nameDraft, setNameDraft] = useState("");
  const [descriptionDraft, setDescriptionDraft] = useState("");
  const [interpretation, setInterpretation] = useState<ScenarioInterpretResponse | null>(null);

  function load() {
    getScenario(id)
      .then((s) => {
        setScenario(s);
        setNameDraft(s.name);
        setDescriptionDraft(s.description ?? "");
      })
      .catch(() => setError("Unable to load this scenario."));
  }

  useEffect(() => {
    load();
    getCurrentUser().then(setCurrentUser).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const canAct = currentUser ? CAN_ACT.has(currentUser.role_name) : false;

  async function handleRename() {
    if (!nameDraft.trim()) return;
    setIsBusy(true);
    setError(null);
    try {
      await updateScenario(id, { name: nameDraft.trim(), description: descriptionDraft.trim() || null });
      setIsRenaming(false);
      load();
    } catch {
      setError("Unable to rename this scenario.");
    } finally {
      setIsBusy(false);
    }
  }

  async function handleRerun() {
    setIsBusy(true);
    setError(null);
    try {
      await rerunScenario(id);
      load();
    } catch {
      setError("Unable to rerun this scenario against current data.");
    } finally {
      setIsBusy(false);
    }
  }

  async function handleInterpret() {
    setIsBusy(true);
    setError(null);
    try {
      const response = await interpretScenario(id);
      setInterpretation(response);
    } catch {
      setError("Unable to generate an AI interpretation right now.");
    } finally {
      setIsBusy(false);
    }
  }

  async function handleDelete() {
    if (!window.confirm("Delete this scenario? This cannot be undone.")) return;
    setIsBusy(true);
    try {
      await deleteScenario(id);
      router.push("/what-if-simulator/scenarios");
    } catch {
      setError("Unable to delete this scenario.");
      setIsBusy(false);
    }
  }

  if (!scenario) {
    return (
      <div className="flex flex-1 flex-col gap-6">
        <PageHeader title="Scenario" description="Loading…" />
        {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}
      </div>
    );
  }

  const results = scenario.results;

  return (
    <div className="flex flex-1 flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        {isRenaming ? (
          <div className="flex flex-1 flex-col gap-2">
            <input
              value={nameDraft}
              onChange={(e) => setNameDraft(e.target.value)}
              className="rounded-md border border-zinc-300 px-3 py-2 text-lg font-semibold dark:border-zinc-700 dark:bg-zinc-900"
            />
            <input
              value={descriptionDraft}
              onChange={(e) => setDescriptionDraft(e.target.value)}
              placeholder="Description (optional)"
              className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
            />
            <div className="flex gap-2">
              <button type="button" onClick={handleRename} disabled={isBusy} className="rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900">
                Save Name
              </button>
              <button type="button" onClick={() => setIsRenaming(false)} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900">
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <PageHeader
            title={scenario.name}
            description={
              scenario.description ??
              `${scenario.baseline_date_from} to ${scenario.baseline_date_to} · ${
                [scenario.field_name, scenario.facility_name, scenario.well_code, scenario.equipment_tag].filter(Boolean).join(" / ") || "All scope"
              }`
            }
          />
        )}
      </div>

      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

      {canAct ? (
        <div className="flex flex-wrap gap-2">
          {!isRenaming ? (
            <button type="button" onClick={() => setIsRenaming(true)} disabled={isBusy} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-900">
              Rename
            </button>
          ) : null}
          <button type="button" onClick={handleRerun} disabled={isBusy} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-900">
            {isBusy ? "Working…" : "Rerun Against Current Data"}
          </button>
          <button type="button" onClick={handleInterpret} disabled={isBusy || !scenario.results} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-900">
            {interpretation ? "Regenerate AI Interpretation" : "Add AI Interpretation"}
          </button>
          <button type="button" onClick={handleDelete} disabled={isBusy} className="rounded-md border border-red-300 px-3 py-1.5 text-sm font-medium text-red-600 hover:bg-red-50 disabled:opacity-50 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-950/40">
            Delete
          </button>
        </div>
      ) : null}

      <p className="text-xs text-zinc-400 dark:text-zinc-500">
        Calculation version {scenario.calculation_version} · Last run{" "}
        {scenario.last_run_at ? scenario.last_run_at.slice(0, 19).replace("T", " ") : "never"}
      </p>

      {!results ? (
        <p className="text-sm text-zinc-500 dark:text-zinc-400">This scenario has not been run yet.</p>
      ) : (
        <>
          <GuardrailBanner flags={results.guardrail_flags} />

          {!results.baseline.data_sufficient ? (
            <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
              Insufficient historical data to calculate this scenario reliably. {results.baseline.missing_data_note}
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <KpiCard label="Baseline Oil Production" value={results.baseline.oil_bbl.toLocaleString()} unit="bbl" />
                <KpiCard label="Scenario Oil Production" value={results.scenario.oil_bbl.toLocaleString()} unit="bbl" calculated />
                <KpiCard
                  label="Est. Production Recovery (Downtime)"
                  value={results.scenario.recovered_production_bbl.toLocaleString()}
                  unit="bbl"
                  hint="Estimate — not guaranteed"
                  calculated
                />
                <KpiCard
                  label="Est. Production Recovery (Loss Reduction)"
                  value={results.scenario.potential_loss_reduction_oil_bbl.toLocaleString()}
                  unit="bbl"
                  hint="Estimate — not guaranteed"
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

              <section>
                <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-50">Baseline vs. Scenario</h3>
                <ScenarioComparisonCharts rows={results.comparison} />
                <div className="mt-4">
                  <ComparisonTable rows={results.comparison} />
                </div>
              </section>
            </>
          )}
        </>
      )}

      {interpretation ? (
        <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">
            AI Interpretation ({interpretation.provider}
            {interpretation.model ? ` / ${interpretation.model}` : ""})
          </h3>
          <p className="mt-2 whitespace-pre-wrap text-sm text-zinc-700 dark:text-zinc-300">{interpretation.interpretation}</p>
        </div>
      ) : null}

      {results ? <p className="text-xs text-zinc-400 dark:text-zinc-500">{scenario.disclaimer_text}</p> : null}

      <p className="text-xs text-zinc-400 dark:text-zinc-500">
        <Link href="/what-if-simulator/scenarios" className="underline-offset-2 hover:underline">
          Back to saved scenarios
        </Link>
      </p>
    </div>
  );
}
