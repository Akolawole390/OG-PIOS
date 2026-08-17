import Link from "next/link";
import type { ReactNode } from "react";
import { BarChart, type BarDatum } from "@/components/charts/BarChart";
import { TrendChart } from "@/components/charts/TrendChart";
import { HealthDistributionChart } from "@/components/charts/HealthDistributionChart";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { ComparisonTable } from "@/components/what-if/ComparisonTable";
import { MoneyStat } from "@/components/what-if/MoneyStat";
import { ScenarioComparisonCharts } from "@/components/what-if/ScenarioComparisonCharts";
import type { ReportResults, ReportSections } from "@/lib/api";

function formatNumber(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString(undefined, { maximumFractionDigits: digits });
}

function SectionCard({ title, source, children }: { title: string; source?: string; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-50">{title}</h3>
      {children}
      {source ? <p className="mt-3 text-xs text-zinc-400 dark:text-zinc-500">{source}</p> : null}
    </section>
  );
}

function Traceability({ traceability }: { traceability?: { source_module: string; methodology: string; record_count: number | null } }) {
  if (!traceability) return null;
  return (
    <p className="mt-3 text-xs text-zinc-400 dark:text-zinc-500">
      Source: {traceability.source_module} — {traceability.methodology}
      {traceability.record_count !== null && traceability.record_count !== undefined ? ` (${traceability.record_count} record(s))` : ""}
    </p>
  );
}

function ProductionSection({ section }: { section: NonNullable<ReportSections["production"]> }) {
  const k = section.kpis;
  return (
    <SectionCard title="Production">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard label="Oil Production" value={formatNumber(k.total_oil_bbl)} unit="bbl" />
        <KpiCard label="Gas Production" value={formatNumber(k.total_gas_mscf)} unit="mscf" />
        <KpiCard label="Water Production" value={formatNumber(k.total_water_bbl)} unit="bbl" />
        <KpiCard label="BOE" value={formatNumber(k.boe)} unit="boe" calculated />
        <KpiCard label="Producing Wells" value={String(k.producing_wells_count)} />
        <KpiCard label="Target Oil Rate" value={formatNumber(k.target_oil_bopd)} unit="bopd" />
        <KpiCard label="Target Variance" value={k.target_variance_pct !== null ? `${formatNumber(k.target_variance_pct)}%` : "—"} calculated />
        <KpiCard label="Water Cut" value={k.avg_water_cut_pct !== null ? `${formatNumber(k.avg_water_cut_pct)}%` : "—"} calculated />
      </div>
      <Traceability traceability={section._traceability} />
    </SectionCard>
  );
}

function EquipmentSection({ section }: { section: NonNullable<ReportSections["equipment"]> }) {
  const buckets = Object.entries(section.health_band_counts).map(([band, count]) => ({ band, count }));
  return (
    <SectionCard title="Equipment">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div>
          <KpiCard label="Total Equipment" value={String(section.total_equipment)} />
          <div className="mt-4">
            <HealthDistributionChart title="Health Distribution" buckets={buckets} />
          </div>
        </div>
        <div>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            Critical Equipment
          </h4>
          {section.critical_equipment.length === 0 ? (
            <p className="text-sm text-zinc-500 dark:text-zinc-400">No critical equipment.</p>
          ) : (
            <ul className="flex flex-col gap-1.5 text-sm">
              {section.critical_equipment.map((eq) => (
                <li key={eq.id} className="flex justify-between rounded border border-zinc-200 px-2 py-1 dark:border-zinc-800">
                  <span>{eq.equipment_tag}</span>
                  <span className="text-zinc-500 dark:text-zinc-400">{eq.status} · {formatNumber(eq.health_score)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
      <Traceability traceability={section._traceability} />
    </SectionCard>
  );
}

function MaintenanceSection({ section }: { section: NonNullable<ReportSections["maintenance"]> }) {
  return (
    <SectionCard title="Maintenance">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard label="Work Orders" value={String(section.record_count)} />
        <KpiCard label="Total Cost" value={`$${formatNumber(section.total_cost, 0)}`} />
        <KpiCard label="Total Downtime" value={formatNumber(section.total_downtime_hours)} unit="hrs" />
        <KpiCard label="Preventive" value={String(section.preventive_count)} />
        <KpiCard label="Corrective" value={String(section.corrective_count)} />
        <KpiCard label="Emergency" value={String(section.emergency_count)} />
        <KpiCard label="Overdue" value={String(section.overdue.length)} />
        <KpiCard label="Due Today" value={String(section.due_today.length)} />
      </div>
      <Traceability traceability={section._traceability} />
    </SectionCard>
  );
}

function ProductionLossSection({ section }: { section: NonNullable<ReportSections["production_loss"]> }) {
  const wellBars: BarDatum[] = section.top_affected_wells.map((w) => ({ key: w.well_code, label: w.well_code, value: w.estimated_revenue_impact }));
  return (
    <SectionCard title="Production Loss">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard label="Loss Events" value={String(section.event_count)} />
        <KpiCard label="Oil Lost" value={formatNumber(section.total_oil_bopd_lost)} unit="bbl" calculated />
        <KpiCard label="Gas Lost" value={formatNumber(section.total_gas_mscfd_lost)} unit="mscf" calculated />
        <KpiCard label="Downtime" value={formatNumber(section.total_downtime_hours)} unit="hrs" />
      </div>
      <div className="mt-4">
        <MoneyStat label="Estimated Revenue Impact" amounts={section.estimated_revenue_impact} />
      </div>
      {wellBars.length > 0 ? (
        <div className="mt-4">
          <BarChart title="Top Affected Wells (Revenue Impact)" data={wellBars} unit="$" />
        </div>
      ) : null}
      <Traceability traceability={section._traceability} />
    </SectionCard>
  );
}

function EconomicsSection({ section }: { section: NonNullable<ReportSections["economics"]> }) {
  if (section.data_sufficient === false) {
    return (
      <SectionCard title="Economics">
        <p className="text-sm text-amber-700 dark:text-amber-400">{section.missing_data_note}</p>
      </SectionCard>
    );
  }
  return (
    <SectionCard title="Economics">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <MoneyStat label="Estimated Revenue" amounts={section.estimated_revenue ?? []} />
        <MoneyStat label="Operating Cost" amounts={section.operating_cost ?? []} />
        <KpiCard label="Maintenance Cost" value={`$${formatNumber(section.maintenance_cost_usd, 0)}`} />
        <MoneyStat label="Cost per Barrel" amounts={section.cost_per_bbl ?? []} />
        <MoneyStat label="Cost per BOE" amounts={section.cost_per_boe ?? []} />
        <MoneyStat
          label="Estimated Operating Margin"
          amounts={section.estimated_operating_margin ?? []}
          hint={section.margin_currency_mismatch ? "Currency mismatch — some costs have no matching revenue currency" : undefined}
        />
      </div>
      <Traceability traceability={section._traceability} />
    </SectionCard>
  );
}

function AlertsSection({ section }: { section: NonNullable<ReportSections["alerts"]> }) {
  return (
    <SectionCard title="Alerts">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard label="Total Alerts" value={String(section.total)} />
        <KpiCard label="Critical" value={String(section.critical_count)} />
        <KpiCard label="High" value={String(section.high_count)} />
        <KpiCard label="Open" value={String(section.open_count)} />
        <KpiCard label="Resolved" value={String(section.resolved_count)} />
      </div>
      {section.recent.length > 0 ? (
        <ul className="mt-4 flex flex-col gap-1.5 text-sm">
          {section.recent.map((a) => (
            <li key={a.id} className="flex justify-between rounded border border-zinc-200 px-2 py-1 dark:border-zinc-800">
              <span>{a.title}</span>
              <span className="text-zinc-500 dark:text-zinc-400">{a.severity}</span>
            </li>
          ))}
        </ul>
      ) : null}
      <Traceability traceability={section._traceability} />
    </SectionCard>
  );
}

function AiInsightsSection({ section }: { section: NonNullable<ReportSections["ai_insights"]> }) {
  return (
    <SectionCard title="AI Insights">
      <KpiCard label="Total Insights" value={String(section.total)} />
      <ul className="mt-4 flex flex-col gap-3">
        {section.highest_priority.map((insight) => (
          <li key={insight.id} className="rounded-md border border-zinc-200 p-3 text-sm dark:border-zinc-800">
            <div className="flex items-center justify-between">
              <span className="font-medium text-zinc-900 dark:text-zinc-50">{insight.title}</span>
              <span className="text-xs text-zinc-500 dark:text-zinc-400">{insight.severity} · {insight.confidence_level} confidence</span>
            </div>
            <p className="mt-1 text-zinc-600 dark:text-zinc-400">{insight.summary}</p>
            {insight.recommended_investigation ? (
              <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">Investigate: {insight.recommended_investigation}</p>
            ) : null}
          </li>
        ))}
      </ul>
      <Traceability traceability={section._traceability} />
    </SectionCard>
  );
}

function ProductionTrendSection({ section }: { section: NonNullable<ReportSections["production_trend"]> }) {
  return (
    <SectionCard title="Production Trend">
      <TrendChart
        title="Daily Production"
        data={section.points as Record<string, number | string | null>[]}
        xKey="record_date"
        showTableToggle
        series={[
          { key: "oil_bopd", label: "Oil", unit: "bopd", color: "var(--chart-series-1)" },
          { key: "gas_mscfd", label: "Gas", unit: "mscfd", color: "var(--chart-series-2)" },
          { key: "water_bwpd", label: "Water", unit: "bwpd", color: "var(--chart-series-3)" },
        ]}
      />
      <Traceability traceability={section._traceability} />
    </SectionCard>
  );
}

function ProductionByScopeSection({ section }: { section: NonNullable<ReportSections["production_by_scope"]> }) {
  return (
    <SectionCard title="Production by Scope">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <BarChart title="By Field (bopd)" data={section.by_field.map((b) => ({ key: b.key, label: b.label, value: b.oil_bopd }))} unit="bopd" />
        <BarChart title="By Facility (bopd)" data={section.by_facility.map((b) => ({ key: b.key, label: b.label, value: b.oil_bopd }))} unit="bopd" />
        <BarChart title="Top Wells (bopd)" data={section.top_wells.map((b) => ({ key: b.key, label: b.label, value: b.oil_bopd }))} unit="bopd" />
        <BarChart title="Lowest-Performing Wells (bopd)" data={section.lowest_wells.map((b) => ({ key: b.key, label: b.label, value: b.oil_bopd }))} unit="bopd" />
      </div>
      <Traceability traceability={section._traceability} />
    </SectionCard>
  );
}

function ActualVsTargetSection({ section }: { section: NonNullable<ReportSections["actual_vs_target"]> }) {
  return (
    <SectionCard title="Actual vs. Target">
      <TrendChart
        title="Actual Oil vs. Target"
        data={section.points as unknown as Record<string, number | string | null>[]}
        xKey="record_date"
        showTableToggle
        series={[
          { key: "actual_oil_bopd", label: "Actual", unit: "bopd", color: "var(--chart-series-1)" },
          { key: "target_oil_bopd", label: "Target", unit: "bopd", color: "var(--chart-series-2)" },
        ]}
      />
      <Traceability traceability={section._traceability} />
    </SectionCard>
  );
}

function ExecutiveSummarySection({ section }: { section: NonNullable<ReportSections["executive_summary"]> }) {
  return (
    <SectionCard title="Executive Summary">
      <div className="flex flex-col gap-4 text-sm">
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">What Happened?</h4>
          <p className="mt-1 text-zinc-700 dark:text-zinc-300">{section.what_happened}</p>
        </div>
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">Why It Matters</h4>
          <p className="mt-1 text-zinc-700 dark:text-zinc-300">{section.why_it_matters}</p>
        </div>
        {section.biggest_risks.length > 0 ? (
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">Biggest Risks</h4>
            <ul className="mt-1 list-disc pl-5 text-zinc-700 dark:text-zinc-300">
              {section.biggest_risks.map((r, i) => <li key={i}>{r}</li>)}
            </ul>
          </div>
        ) : null}
        {section.biggest_opportunities.length > 0 ? (
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">Biggest Opportunities</h4>
            <ul className="mt-1 list-disc pl-5 text-zinc-700 dark:text-zinc-300">
              {section.biggest_opportunities.map((r, i) => <li key={i}>{r}</li>)}
            </ul>
          </div>
        ) : null}
        {section.recommended_investigations.length > 0 ? (
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">Recommended Investigations</h4>
            <ul className="mt-1 list-disc pl-5 text-zinc-700 dark:text-zinc-300">
              {section.recommended_investigations.map((r, i) => <li key={i}>{r}</li>)}
            </ul>
          </div>
        ) : null}
      </div>
    </SectionCard>
  );
}

function ScenarioSection({ section }: { section: NonNullable<ReportSections["scenario"]> }) {
  const results = section.results;
  return (
    <SectionCard title="What-If Scenario">
      <div className="flex items-center justify-between">
        <div>
          <h4 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">{section.scenario_name}</h4>
          <span className="inline-block rounded border border-zinc-300 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-zinc-500 dark:border-zinc-700 dark:text-zinc-400">
            {section.label}
          </span>
        </div>
        <Link href={`/what-if-simulator/scenarios/${section.scenario_id}`} className="text-sm text-zinc-600 underline-offset-2 hover:underline dark:text-zinc-400">
          View full scenario →
        </Link>
      </div>
      {!results ? (
        <p className="mt-3 text-sm text-zinc-500 dark:text-zinc-400">This scenario has not been run yet.</p>
      ) : !results.baseline.data_sufficient ? (
        <p className="mt-3 text-sm text-amber-700 dark:text-amber-400">{results.baseline.missing_data_note}</p>
      ) : (
        <div className="mt-4 flex flex-col gap-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCard label="Baseline Production" value={formatNumber(results.baseline.oil_bbl)} unit="bbl" />
            <KpiCard label="Scenario Production" value={formatNumber(results.scenario.oil_bbl)} unit="bbl" calculated />
            <MoneyStat label="Baseline Revenue" amounts={results.baseline.revenue} />
            <MoneyStat label="Scenario Revenue" amounts={results.scenario.revenue} />
          </div>
          <ScenarioComparisonCharts rows={results.comparison} />
          <ComparisonTable rows={results.comparison} />
        </div>
      )}
      <Traceability traceability={section._traceability} />
    </SectionCard>
  );
}

/** Switches on report_type/section key, rendering every section with EXISTING components only —
 * KpiCard, MoneyStat, MultiCurrencyAmount, ComparisonTable, BarChart, TrendChart,
 * HealthDistributionChart, and ScenarioComparisonCharts (for the What-If report type). Zero new
 * chart components were needed for this module. */
export function ReportViewer({ results }: { results: ReportResults }) {
  const sections = results.sections;

  if (results.data_sufficient === false) {
    return (
      <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
        {results.missing_data_note}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {sections.executive_summary ? <ExecutiveSummarySection section={sections.executive_summary} /> : null}
      {sections.production ? <ProductionSection section={sections.production} /> : null}
      {sections.production_trend ? <ProductionTrendSection section={sections.production_trend} /> : null}
      {sections.production_by_scope ? <ProductionByScopeSection section={sections.production_by_scope} /> : null}
      {sections.actual_vs_target ? <ActualVsTargetSection section={sections.actual_vs_target} /> : null}
      {sections.equipment ? <EquipmentSection section={sections.equipment} /> : null}
      {sections.maintenance ? <MaintenanceSection section={sections.maintenance} /> : null}
      {sections.production_loss ? <ProductionLossSection section={sections.production_loss} /> : null}
      {sections.economics ? <EconomicsSection section={sections.economics} /> : null}
      {sections.alerts ? <AlertsSection section={sections.alerts} /> : null}
      {sections.ai_insights ? <AiInsightsSection section={sections.ai_insights} /> : null}
      {sections.scenario ? <ScenarioSection section={sections.scenario} /> : null}

      {results.ai_narrative ? (
        <SectionCard title={`AI Narrative Summary${results.ai_narrative_provider ? ` (${results.ai_narrative_provider})` : ""}`}>
          <p className="whitespace-pre-wrap text-sm text-zinc-700 dark:text-zinc-300">{results.ai_narrative}</p>
        </SectionCard>
      ) : null}

      <p className="text-xs text-zinc-400 dark:text-zinc-500">{results.disclaimer_text}</p>
      <p className="text-xs font-medium text-amber-700 dark:text-amber-400">{results.synthetic_data_disclaimer}</p>
    </div>
  );
}
