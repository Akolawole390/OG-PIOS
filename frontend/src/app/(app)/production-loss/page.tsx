"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { PageHeader } from "@/components/layout/PageHeader";
import { BarChart, type BarDatum } from "@/components/charts/BarChart";
import { TrendChart } from "@/components/charts/TrendChart";
import {
  getProductionLossByScope,
  getProductionLossDashboard,
  getProductionLossTrend,
  type ProductionLossDashboard as ProductionLossDashboardType,
} from "@/lib/api";
import { formatCurrency, formatLabel } from "@/lib/format";

function formatNumber(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString(undefined, { maximumFractionDigits: digits });
}

export default function ProductionLossDashboardPage() {
  const [dashboard, setDashboard] = useState<ProductionLossDashboardType | null>(null);
  const [categoryBars, setCategoryBars] = useState<BarDatum[]>([]);
  const [wellBars, setWellBars] = useState<BarDatum[]>([]);
  const [equipmentBars, setEquipmentBars] = useState<BarDatum[]>([]);
  const [trend, setTrend] = useState<Record<string, number | string | null>[]>([]);
  const [volumeTrend, setVolumeTrend] = useState<Record<string, number | string | null>[]>([]);

  useEffect(() => {
    getProductionLossDashboard().then(setDashboard).catch(() => undefined);
    getProductionLossByScope({ group_by: "category" })
      .then((res) => setCategoryBars(res.bars.map((b) => ({ key: b.key, label: formatLabel(b.label), value: b.count }))))
      .catch(() => undefined);
    getProductionLossByScope({ group_by: "well" })
      .then((res) =>
        setWellBars(res.bars.slice(0, 8).map((b) => ({ key: b.key, label: b.label, value: b.total_revenue_impact }))),
      )
      .catch(() => undefined);
    getProductionLossByScope({ group_by: "equipment" })
      .then((res) =>
        setEquipmentBars(res.bars.slice(0, 8).map((b) => ({ key: b.key, label: b.label, value: b.total_revenue_impact }))),
      )
      .catch(() => undefined);
    getProductionLossTrend()
      .then((res) => {
        setTrend(res.points.map((p) => ({ month: p.month, total_revenue_impact: p.total_revenue_impact })));
        setVolumeTrend(
          res.points.map((p) => ({
            month: p.month,
            total_oil_bopd_lost: p.total_oil_bopd_lost,
            total_gas_mscfd_lost: p.total_gas_mscfd_lost,
          })),
        );
      })
      .catch(() => undefined);
  }, []);

  return (
    <div className="flex flex-1 flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <PageHeader
          title="Production Loss Dashboard"
          description="Estimated production loss and financial impact. All demo data is synthetic."
        />
        <Link
          href="/production-loss/list"
          className="shrink-0 rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
        >
          View All Records
        </Link>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <KpiCard label="Loss Events" value={formatNumber(dashboard?.event_count, 0)} />
        <KpiCard label="Oil Lost" value={formatNumber(dashboard?.total_oil_bopd_lost)} unit="bbl" calculated />
        <KpiCard label="Gas Lost" value={formatNumber(dashboard?.total_gas_mscfd_lost)} unit="mscf" calculated />
        <KpiCard
          label="Revenue Impact"
          value={formatCurrency(dashboard?.total_revenue_impact)}
          hint="Estimate — not a certified financial figure"
          calculated
        />
        <KpiCard label="Avg Downtime" value={formatNumber(dashboard?.avg_downtime_hours)} unit="hrs" calculated />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <BarChart title="Loss Events by Category" data={categoryBars} unit="events" />
        <BarChart title="Revenue Impact by Well (Top 8)" data={wellBars} unit="$" />
        <BarChart title="Revenue Impact by Equipment (Top 8)" data={equipmentBars} unit="$" />
        <TrendChart
          title="Revenue Impact Over Time"
          data={trend}
          xKey="month"
          showTableToggle
          series={[{ key: "total_revenue_impact", label: "Revenue Impact", unit: "$", color: "var(--chart-series-1)" }]}
        />
        <TrendChart
          title="Volume Lost Over Time"
          data={volumeTrend}
          xKey="month"
          showTableToggle
          series={[
            { key: "total_oil_bopd_lost", label: "Oil Lost", unit: "bbl", color: "var(--chart-series-2)" },
            { key: "total_gas_mscfd_lost", label: "Gas Lost", unit: "mscf", color: "var(--chart-series-3)" },
          ]}
        />
      </div>

      {dashboard ? (
        <p className="text-xs text-zinc-400 dark:text-zinc-500">{dashboard.disclaimer_text}</p>
      ) : null}
    </div>
  );
}
