"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { TrendChart } from "@/components/charts/TrendChart";
import { BarChart, type BarDatum } from "@/components/charts/BarChart";
import { MultiCurrencyAmount } from "@/components/cost-revenue/MultiCurrencyAmount";
import {
  getEconomicsByScope,
  getRevenueTrend,
  listFacilities,
  listWells,
  type Facility,
  type MoneyByCurrency,
  type Well,
} from "@/lib/api";

function amountFor(list: MoneyByCurrency[], preferred = "USD"): number | null {
  const match = list.find((m) => m.currency === preferred);
  if (match) return match.amount;
  return list[0]?.amount ?? null;
}

export default function RevenueAnalysisPage() {
  const [facilityId, setFacilityId] = useState("");
  const [wellId, setWellId] = useState("");
  const [commodity, setCommodity] = useState("");
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [wells, setWells] = useState<Well[]>([]);
  const [trend, setTrend] = useState<Record<string, number | string | null>[]>([]);
  const [revenueByField, setRevenueByField] = useState<BarDatum[]>([]);
  const [latestPoint, setLatestPoint] = useState<{ oil: MoneyByCurrency[]; gas: MoneyByCurrency[]; total: MoneyByCurrency[] } | null>(null);

  useEffect(() => {
    listFacilities().then(setFacilities).catch(() => undefined);
    listWells({ page_size: 100, sort: "well_id" }).then((res) => setWells(res.items)).catch(() => undefined);
    getEconomicsByScope({ scope: "field", rank_by: "revenue" })
      .then((res) => setRevenueByField(res.rows.map((r) => ({ key: r.key, label: r.label, value: amountFor(r.revenue) ?? 0 }))))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    getRevenueTrend({
      facility_id: facilityId ? Number(facilityId) : undefined,
      well_id: wellId ? Number(wellId) : undefined,
      commodity: commodity ? (commodity as "oil" | "gas") : undefined,
    })
      .then((res) => {
        setTrend(
          res.points.map((p) => ({
            month: p.month,
            oil_revenue: amountFor(p.oil_revenue),
            gas_revenue: amountFor(p.gas_revenue),
            total_revenue: amountFor(p.total_revenue),
          })),
        );
        const last = res.points[res.points.length - 1];
        setLatestPoint(last ? { oil: last.oil_revenue, gas: last.gas_revenue, total: last.total_revenue } : null);
      })
      .catch(() => undefined);
  }, [facilityId, wellId, commodity]);

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader title="Revenue Analysis" description="Estimated revenue = production volume × commodity price, using the existing CommodityPrice infrastructure." />

      <div className="flex flex-wrap items-center gap-3">
        <select value={facilityId} onChange={(e) => setFacilityId(e.target.value)} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          <option value="">All facilities</option>
          {facilities.map((f) => (
            <option key={f.id} value={f.id}>{f.name}</option>
          ))}
        </select>
        <select value={wellId} onChange={(e) => setWellId(e.target.value)} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          <option value="">All wells</option>
          {wells.map((w) => (
            <option key={w.id} value={w.id}>{w.well_id}</option>
          ))}
        </select>
        <select value={commodity} onChange={(e) => setCommodity(e.target.value)} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          <option value="">Oil + Gas</option>
          <option value="oil">Oil only</option>
          <option value="gas">Gas only</option>
        </select>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <p className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">Latest Month Oil Revenue</p>
          <p className="mt-2 text-xl font-semibold text-zinc-900 dark:text-zinc-50"><MultiCurrencyAmount amounts={latestPoint?.oil ?? []} /></p>
        </div>
        <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <p className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">Latest Month Gas Revenue</p>
          <p className="mt-2 text-xl font-semibold text-zinc-900 dark:text-zinc-50"><MultiCurrencyAmount amounts={latestPoint?.gas ?? []} /></p>
        </div>
        <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <p className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">Latest Month Total Revenue</p>
          <p className="mt-2 text-xl font-semibold text-zinc-900 dark:text-zinc-50"><MultiCurrencyAmount amounts={latestPoint?.total ?? []} /></p>
        </div>
      </div>

      <TrendChart
        title="Revenue Over Time (dominant currency)"
        data={trend}
        xKey="month"
        showTableToggle
        series={[
          { key: "oil_revenue", label: "Oil Revenue", color: "var(--chart-series-1)" },
          { key: "gas_revenue", label: "Gas Revenue", color: "var(--chart-series-2)" },
          { key: "total_revenue", label: "Total Revenue", color: "var(--chart-series-3)" },
        ]}
      />

      <BarChart title="Estimated Revenue by Field (Latest Month, dominant currency)" data={revenueByField} unit="$" />

      <p className="text-xs text-zinc-400 dark:text-zinc-500">
        Revenue is always clearly labeled &quot;Estimated Revenue&quot; — never presented as an audited financial
        figure. Charts show each series&apos; dominant currency (USD where present); see individual records for
        exact per-currency amounts.
      </p>
    </div>
  );
}
