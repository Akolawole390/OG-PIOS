"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { PageHeader } from "@/components/layout/PageHeader";
import { BarChart, type BarDatum } from "@/components/charts/BarChart";
import { TrendChart } from "@/components/charts/TrendChart";
import {
  getProductionByScope,
  getProductionIssues,
  getProductionKpis,
  getProductionTrends,
  type ProductionIssuesResponse,
  type ProductionKpis as ProductionKpisType,
} from "@/lib/api";

function formatNumber(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString(undefined, { maximumFractionDigits: digits });
}

export default function ProductionDashboardPage() {
  const [kpis, setKpis] = useState<ProductionKpisType | null>(null);
  const [trend, setTrend] = useState<Record<string, number | string | null>[]>([]);
  const [waterCut, setWaterCut] = useState<Record<string, number | string | null>[]>([]);
  const [topWells, setTopWells] = useState<BarDatum[]>([]);
  const [lowestWells, setLowestWells] = useState<BarDatum[]>([]);
  const [issues, setIssues] = useState<ProductionIssuesResponse | null>(null);

  useEffect(() => {
    getProductionKpis().then(setKpis).catch(() => undefined);
    getProductionTrends("oil_gas_water").then((r) => setTrend(r.points)).catch(() => undefined);
    getProductionTrends("water_cut").then((r) => setWaterCut(r.points)).catch(() => undefined);
    getProductionByScope({ group_by: "well", order: "desc", limit: 5 })
      .then((res) => setTopWells(res.bars.map((b) => ({ key: b.key, label: b.label, value: b.oil_bopd }))))
      .catch(() => undefined);
    getProductionByScope({ group_by: "well", order: "asc", limit: 5 })
      .then((res) => setLowestWells(res.bars.map((b) => ({ key: b.key, label: b.label, value: b.oil_bopd }))))
      .catch(() => undefined);
    getProductionIssues().then(setIssues).catch(() => undefined);
  }, []);

  return (
    <div className="flex flex-1 flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <PageHeader
          title="Production Dashboard"
          description="Fleet-wide production overview. All demo data is synthetic."
        />
        <div className="flex shrink-0 gap-2">
          <Link
            href="/production/records"
            className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
          >
            View Records
          </Link>
          <Link
            href="/production/analytics"
            className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
          >
            Full Analytics
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard label="Oil Production" value={formatNumber(kpis?.total_oil_bbl)} unit="bbl" />
        <KpiCard label="Gas Production" value={formatNumber(kpis?.total_gas_mscf)} unit="mscf" />
        <KpiCard label="Water Production" value={formatNumber(kpis?.total_water_bbl)} unit="bbl" />
        <KpiCard label="BOE" value={formatNumber(kpis?.boe)} unit="boe" calculated />
        <KpiCard label="Producing Wells" value={formatNumber(kpis?.producing_wells_count, 0)} />
        <KpiCard label="Avg Water Cut" value={formatNumber(kpis?.avg_water_cut_pct)} unit="%" calculated />
        <KpiCard label="Avg GOR" value={formatNumber(kpis?.avg_gor)} unit="scf/bbl" calculated />
        <KpiCard
          label="Target Variance"
          value={kpis?.target_variance_pct !== null && kpis?.target_variance_pct !== undefined ? `${formatNumber(kpis.target_variance_pct)}%` : "—"}
          hint={kpis?.reference_date ? `As of ${kpis.reference_date}` : undefined}
          calculated
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <TrendChart
          title="Production Trend"
          data={trend}
          xKey="record_date"
          showTableToggle
          series={[
            { key: "oil_bopd", label: "Oil", unit: "BOPD", color: "var(--chart-series-1)" },
            { key: "gas_mscfd", label: "Gas", unit: "MSCFD", color: "var(--chart-series-2)" },
            { key: "water_bwpd", label: "Water", unit: "BWPD", color: "var(--chart-series-3)" },
          ]}
        />
        <TrendChart
          title="Water-Cut Trend"
          data={waterCut}
          xKey="record_date"
          series={[{ key: "water_cut_pct", label: "Water Cut", unit: "%", color: "var(--chart-series-1)" }]}
        />
        <BarChart title="Top Producing Wells (Oil, BOPD)" data={topWells} unit="BOPD" />
        <BarChart title="Lowest Performing Wells (Oil, BOPD)" data={lowestWells} unit="BOPD" />
      </div>

      <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Active Production Issues</h3>
        <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
          Rule-based checks — not anomaly detection. {issues?.reference_date ? `As of ${issues.reference_date}.` : ""}
        </p>
        <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
              Currently Down ({issues?.down_wells.length ?? 0})
            </p>
            {issues && issues.down_wells.length > 0 ? (
              <ul className="mt-2 space-y-1 text-sm">
                {issues.down_wells.map((w) => (
                  <li key={w.well_id}>
                    <Link href={`/wells/${w.well_id}`} className="text-zinc-900 hover:underline dark:text-zinc-50">
                      {w.well_code}
                    </Link>{" "}
                    <span className="text-zinc-500 dark:text-zinc-400">— {w.detail}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">None.</p>
            )}
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
              Zero Production Today ({issues?.zero_production_wells.length ?? 0})
            </p>
            {issues && issues.zero_production_wells.length > 0 ? (
              <ul className="mt-2 space-y-1 text-sm">
                {issues.zero_production_wells.map((w) => (
                  <li key={w.well_id}>
                    <Link href={`/wells/${w.well_id}`} className="text-zinc-900 hover:underline dark:text-zinc-50">
                      {w.well_code}
                    </Link>{" "}
                    <span className="text-zinc-500 dark:text-zinc-400">— {w.detail}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">None.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
