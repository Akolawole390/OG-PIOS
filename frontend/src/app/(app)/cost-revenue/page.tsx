"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { PageHeader } from "@/components/layout/PageHeader";
import { MultiCurrencyAmount } from "@/components/cost-revenue/MultiCurrencyAmount";
import {
  getCostAlerts,
  getCostRevenueDashboard,
  type CostAlert,
  type CostRevenueDashboard as CostRevenueDashboardType,
  type MoneyByCurrency,
} from "@/lib/api";

function formatNumber(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString(undefined, { maximumFractionDigits: digits });
}

const SEVERITY_STYLES: Record<string, string> = {
  info: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  warning: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  critical: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
};

function MoneyStat({ label, amounts, hint }: { label: string; amounts: MoneyByCurrency[]; hint?: string }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex items-center gap-1.5">
        <p className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">{label}</p>
        <span className="rounded border border-zinc-300 px-1 text-[10px] font-medium uppercase tracking-wide text-zinc-400 dark:border-zinc-700 dark:text-zinc-500">
          Estimate
        </span>
      </div>
      <p className="mt-2 text-xl font-semibold text-zinc-900 dark:text-zinc-50">
        <MultiCurrencyAmount amounts={amounts} />
      </p>
      {hint ? <p className="mt-1 text-xs text-zinc-400 dark:text-zinc-500">{hint}</p> : null}
    </div>
  );
}

export default function CostRevenueDashboardPage() {
  const [dashboard, setDashboard] = useState<CostRevenueDashboardType | null>(null);
  const [alerts, setAlerts] = useState<CostAlert[]>([]);

  useEffect(() => {
    getCostRevenueDashboard().then(setDashboard).catch(() => undefined);
    getCostAlerts().then((res) => setAlerts(res.alerts)).catch(() => undefined);
  }, []);

  return (
    <div className="flex flex-1 flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <PageHeader
          title="Cost & Revenue Dashboard"
          description={
            dashboard
              ? `Estimates for ${dashboard.period_start} to ${dashboard.period_end}. All demo data is synthetic.`
              : "Production economics: revenue, cost, and estimated margin."
          }
        />
        <div className="flex shrink-0 gap-2">
          <Link href="/cost-revenue/operating-costs" className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900">
            Operating Costs
          </Link>
          <Link href="/cost-revenue/trends" className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900">
            Trends
          </Link>
        </div>
      </div>

      <section>
        <h2 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-50">Production</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <KpiCard label="Oil Production" value={formatNumber(dashboard?.production.oil_bbl)} unit="bbl" />
          <KpiCard label="Gas Production" value={formatNumber(dashboard?.production.gas_mscf)} unit="mscf" />
          <KpiCard label="BOE" value={formatNumber(dashboard?.production.boe)} unit="boe" calculated />
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-50">Revenue</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <MoneyStat label="Estimated Oil Revenue" amounts={dashboard?.revenue.oil ?? []} />
          <MoneyStat label="Estimated Gas Revenue" amounts={dashboard?.revenue.gas ?? []} />
          <MoneyStat label="Total Estimated Revenue" amounts={dashboard?.revenue.total ?? []} />
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-50">Costs</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <MoneyStat label="Operating Cost" amounts={dashboard?.costs.operating ?? []} />
          <MoneyStat label="Maintenance Cost" amounts={dashboard?.costs.maintenance ?? []} hint="Assumed USD (Maintenance module has no currency field)" />
          <MoneyStat label="Energy Cost" amounts={dashboard?.costs.energy ?? []} />
          <MoneyStat label="Other Costs" amounts={dashboard?.costs.other ?? []} />
          <MoneyStat label="Total Operating Cost" amounts={dashboard?.costs.total ?? []} />
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-50">Economics</h2>
        {dashboard?.economics.currency_mismatch ? (
          <p className="mb-3 rounded-md border border-amber-300 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
            Revenue and cost this period are in different currencies with no overlap — margin cannot be computed
            without inventing an exchange rate, so it is intentionally left blank rather than estimated.
          </p>
        ) : null}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <MoneyStat label="Estimated Operating Margin" amounts={dashboard?.economics.margin ?? []} />
          <MoneyStat label="Cost per Barrel" amounts={dashboard?.economics.cost_per_bbl ?? []} />
          <MoneyStat label="Cost per BOE" amounts={dashboard?.economics.cost_per_boe ?? []} />
          <MoneyStat label="Revenue per Barrel" amounts={dashboard?.economics.revenue_per_bbl ?? []} />
          <MoneyStat label="Revenue per BOE" amounts={dashboard?.economics.revenue_per_boe ?? []} />
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-50">Production Loss</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <KpiCard label="Estimated Lost Production" value={formatNumber(dashboard?.production_loss.estimated_lost_oil_bbl)} unit="bbl" calculated />
          <MoneyStat label="Estimated Lost Revenue" amounts={dashboard?.production_loss.estimated_lost_revenue ?? []} />
          <KpiCard label="Downtime" value={formatNumber(dashboard?.production_loss.downtime_hours)} unit="hrs" />
        </div>
        <p className="mt-2 text-xs text-zinc-400 dark:text-zinc-500">
          Read directly from the Production Loss module&apos;s own estimates — never recomputed here, to avoid
          double counting. See <Link href="/production-loss" className="underline">Production Loss</Link> for detail.
        </p>
      </section>

      <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Cost Alerts</h3>
        <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
          Rule-based informational flags — not AI-driven anomaly detection.
        </p>
        {alerts.length > 0 ? (
          <ul className="mt-3 space-y-2 text-sm">
            {alerts.map((alert, index) => (
              <li key={index} className="flex items-start justify-between gap-3 border-b border-zinc-100 pb-2 last:border-0 dark:border-zinc-900">
                <div>
                  <p className="font-medium text-zinc-900 dark:text-zinc-50">
                    {alert.scope_label} — {alert.message}
                  </p>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400">{alert.detail}</p>
                </div>
                <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${SEVERITY_STYLES[alert.severity] ?? SEVERITY_STYLES.info}`}>
                  {alert.severity}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-sm text-zinc-500 dark:text-zinc-400">No cost alerts at this time.</p>
        )}
      </div>

      {dashboard ? <p className="text-xs text-zinc-400 dark:text-zinc-500">{dashboard.disclaimer_text}</p> : null}
    </div>
  );
}
