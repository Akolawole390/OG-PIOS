"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { DashboardHero } from "@/components/dashboard/DashboardHero";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { TrendChart } from "@/components/charts/TrendChart";
import { BarChart, type BarDatum } from "@/components/charts/BarChart";
import { HealthDistributionChart } from "@/components/charts/HealthDistributionChart";
import { AlertSeverityBadge } from "@/components/alerts/AlertSeverityBadge";
import { ConfidenceBadge } from "@/components/ai-insights/ConfidenceBadge";
import { formatCurrency, formatLabel } from "@/lib/format";
import {
  getAlertSummary,
  getCostRevenueDashboard,
  getEquipmentDashboard,
  getInsightSummary,
  getMaintenanceDashboard,
  getProductionKpis,
  getProductionLossDashboard,
  getProductionTrends,
  type AlertSummaryResponse,
  type CostRevenueDashboard,
  type EquipmentDashboard,
  type InsightSummary,
  type MaintenanceDashboard,
  type ProductionKpis,
  type ProductionLossDashboard,
  type TrendResponse,
} from "@/lib/api";

function formatNumber(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString(undefined, { maximumFractionDigits: digits });
}

function firstMoney(entries: { currency: string; amount: number }[] | undefined): string {
  if (!entries || entries.length === 0) return "—";
  return formatCurrency(entries[0].amount, entries[0].currency);
}

export default function DashboardPage() {
  const [kpis, setKpis] = useState<ProductionKpis | null>(null);
  const [alertSummary, setAlertSummary] = useState<AlertSummaryResponse | null>(null);
  const [costRevenue, setCostRevenue] = useState<CostRevenueDashboard | null>(null);
  const [trend, setTrend] = useState<TrendResponse | null>(null);
  const [equipment, setEquipment] = useState<EquipmentDashboard | null>(null);
  const [productionLoss, setProductionLoss] = useState<ProductionLossDashboard | null>(null);
  const [maintenance, setMaintenance] = useState<MaintenanceDashboard | null>(null);
  const [insightSummary, setInsightSummary] = useState<InsightSummary | null>(null);

  useEffect(() => {
    getProductionKpis().then(setKpis).catch(() => undefined);
    getAlertSummary().then(setAlertSummary).catch(() => undefined);
    getCostRevenueDashboard().then(setCostRevenue).catch(() => undefined);
    getProductionTrends("oil_gas_water").then(setTrend).catch(() => undefined);
    getEquipmentDashboard().then(setEquipment).catch(() => undefined);
    getProductionLossDashboard().then(setProductionLoss).catch(() => undefined);
    getMaintenanceDashboard().then(setMaintenance).catch(() => undefined);
    getInsightSummary().then(setInsightSummary).catch(() => undefined);
  }, []);

  const lossByCategory: BarDatum[] = (productionLoss?.by_category ?? []).map((c) => ({
    key: c.category,
    label: formatLabel(c.category),
    value: c.count,
  }));

  return (
    <div className="flex flex-1 flex-col gap-6">
      <DashboardHero
        title="Dashboard"
        description="Executive production overview — live figures from Production, Cost & Revenue, Equipment, Maintenance, Production Loss, Alerts, and AI Insights."
      />

      {/* Hero: current production thesis */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <KpiCard label="Oil Production" value={formatNumber(kpis?.total_oil_bbl)} unit="BOPD" />
        <KpiCard label="Gas Production" value={formatNumber(kpis?.total_gas_mscf)} unit="MSCFD" />
        <KpiCard label="Water Production" value={formatNumber(kpis?.total_water_bbl)} unit="BWPD" />
        <KpiCard label="Producing Wells" value={formatNumber(kpis?.producing_wells_count, 0)} />
        <KpiCard
          label="Target Variance"
          value={
            kpis?.target_variance_pct !== null && kpis?.target_variance_pct !== undefined
              ? `${formatNumber(kpis.target_variance_pct)}%`
              : "—"
          }
          hint={kpis?.reference_date ? `vs. target on ${kpis.reference_date} only — not the full period average` : undefined}
          calculated
        />
      </div>

      {/* Financial & risk: real figures from Cost & Revenue / Production Loss / Alerts */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Link href="/alerts" className="block">
          <KpiCard
            label="Active Alerts"
            value={formatNumber(alertSummary?.open_count, 0)}
            hint={alertSummary ? `${alertSummary.by_severity.critical} critical — view Alert Center` : "View Alert Center"}
          />
        </Link>
        <KpiCard
          label="Estimated Lost Production"
          value={formatNumber(costRevenue?.production_loss.estimated_lost_oil_bbl)}
          unit="bbl"
          hint={costRevenue ? `${formatNumber(costRevenue.production_loss.downtime_hours)} hrs downtime` : undefined}
          calculated
        />
        <KpiCard label="Cost per Barrel" value={firstMoney(costRevenue?.economics.cost_per_bbl)} calculated />
        <KpiCard
          label="Estimated Operating Margin"
          value={firstMoney(costRevenue?.economics.margin)}
          hint={costRevenue?.economics.currency_mismatch ? "Currency mismatch in scope" : undefined}
          calculated
        />
      </div>

      {/* Production trend */}
      <TrendChart
        title="Production Trend"
        data={trend?.points ?? []}
        xKey="record_date"
        showTableToggle
        series={[
          { key: "oil_bopd", label: "Oil", unit: "BOPD", color: "var(--chart-series-1)" },
          { key: "gas_mscfd", label: "Gas", unit: "MSCFD", color: "var(--chart-series-2)" },
          { key: "water_bwpd", label: "Water", unit: "BWPD", color: "var(--chart-series-3)" },
        ]}
      />

      {/* Equipment health + production loss breakdown */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <HealthDistributionChart
          title="Equipment Health Distribution"
          buckets={equipment?.health_distribution.buckets ?? []}
          unscoredCount={equipment?.health_distribution.unscored_count}
        />
        <BarChart title="Production Loss by Category" data={lossByCategory} unit="events" />
      </div>

      {/* Needs attention */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Recent Alerts</h3>
          {alertSummary && alertSummary.recent.length === 0 ? (
            <p className="mt-3 text-sm text-zinc-500 dark:text-zinc-400">No alerts recorded yet.</p>
          ) : (
            <ul className="mt-3 flex flex-col gap-2.5">
              {(alertSummary?.recent ?? []).slice(0, 5).map((alert) => (
                <li key={alert.id} className="flex items-start justify-between gap-2 text-sm">
                  <span className="truncate text-zinc-700 dark:text-zinc-300">{alert.title}</span>
                  <AlertSeverityBadge severity={alert.severity} />
                </li>
              ))}
            </ul>
          )}
          <Link href="/alerts" className="mt-3 inline-block text-xs font-medium text-zinc-600 hover:underline dark:text-zinc-400">
            View all →
          </Link>
        </div>

        <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Critical AI Insights</h3>
          {insightSummary && insightSummary.critical.length === 0 ? (
            <p className="mt-3 text-sm text-zinc-500 dark:text-zinc-400">No critical insights right now.</p>
          ) : (
            <ul className="mt-3 flex flex-col gap-2.5">
              {(insightSummary?.critical ?? []).slice(0, 5).map((insight) => (
                <li key={insight.id} className="flex items-start justify-between gap-2 text-sm">
                  <span className="truncate text-zinc-700 dark:text-zinc-300">{insight.title}</span>
                  <ConfidenceBadge confidence={insight.confidence_level} />
                </li>
              ))}
            </ul>
          )}
          <Link href="/ai-insights" className="mt-3 inline-block text-xs font-medium text-zinc-600 hover:underline dark:text-zinc-400">
            View all →
          </Link>
        </div>

        <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Equipment Requiring Maintenance</h3>
          {maintenance && maintenance.equipment_requiring_maintenance.length === 0 ? (
            <p className="mt-3 text-sm text-zinc-500 dark:text-zinc-400">Nothing due soon.</p>
          ) : (
            <ul className="mt-3 flex flex-col gap-2.5">
              {(maintenance?.equipment_requiring_maintenance ?? []).slice(0, 5).map((item) => (
                <li key={item.equipment_id} className="flex items-center justify-between gap-2 text-sm">
                  <span className="truncate text-zinc-700 dark:text-zinc-300">{item.equipment_name}</span>
                  <span
                    className={`shrink-0 text-xs font-medium ${
                      item.days_from_today < 0 ? "text-red-600 dark:text-red-400" : "text-zinc-400 dark:text-zinc-500"
                    }`}
                  >
                    {item.days_from_today < 0
                      ? `${Math.abs(item.days_from_today)}d overdue`
                      : `${item.days_from_today}d`}
                  </span>
                </li>
              ))}
            </ul>
          )}
          <Link href="/maintenance" className="mt-3 inline-block text-xs font-medium text-zinc-600 hover:underline dark:text-zinc-400">
            View all →
          </Link>
        </div>
      </div>

      {(costRevenue?.disclaimer_text || productionLoss?.disclaimer_text) ? (
        <p className="text-xs text-zinc-400 dark:text-zinc-500">
          {costRevenue?.disclaimer_text ?? productionLoss?.disclaimer_text}
        </p>
      ) : null}
    </div>
  );
}
