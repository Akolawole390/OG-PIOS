"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { TrendChart } from "@/components/charts/TrendChart";
import {
  getMarginTrend,
  getMaintenanceCostTrend,
  getOperatingCostTrend,
  getProductionLossTrend,
  getProductionTrends,
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

type Row = Record<string, number | string | null>;

export default function CostRevenueTrendsPage() {
  const [facilityId, setFacilityId] = useState("");
  const [wellId, setWellId] = useState("");
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [wells, setWells] = useState<Well[]>([]);

  const [revenueRows, setRevenueRows] = useState<Row[]>([]);
  const [costRows, setCostRows] = useState<Row[]>([]);
  const [marginRows, setMarginRows] = useState<Row[]>([]);
  const [productionRows, setProductionRows] = useState<Row[]>([]);
  const [maintenanceCostRows, setMaintenanceCostRows] = useState<Row[]>([]);
  const [lossRows, setLossRows] = useState<Row[]>([]);

  useEffect(() => {
    listFacilities().then(setFacilities).catch(() => undefined);
    listWells({ page_size: 100, sort: "well_id" }).then((res) => setWells(res.items)).catch(() => undefined);
    getProductionTrends("oil_gas_water", {
      facility_id: facilityId ? Number(facilityId) : undefined,
      well_id: wellId ? Number(wellId) : undefined,
    })
      .then((res) => setProductionRows(res.points))
      .catch(() => undefined);
    getMaintenanceCostTrend()
      .then((res) => setMaintenanceCostRows(res.points.map((p) => ({ month: p.month, total_cost: p.total_cost }))))
      .catch(() => undefined);
    getProductionLossTrend()
      .then((res) => setLossRows(res.points.map((p) => ({ month: p.month, total_revenue_impact: p.total_revenue_impact }))))
      .catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const params = { facility_id: facilityId ? Number(facilityId) : undefined, well_id: wellId ? Number(wellId) : undefined };

    getRevenueTrend(params)
      .then((res) =>
        setRevenueRows(
          res.points.map((p) => ({
            month: p.month,
            total_revenue: amountFor(p.total_revenue),
            revenue_per_bbl: amountFor(p.revenue_per_bbl),
          })),
        ),
      )
      .catch(() => undefined);

    getOperatingCostTrend(params)
      .then((res) =>
        setCostRows(
          res.points.map((p) => ({
            month: p.month,
            total_cost: amountFor(p.total_cost),
            cost_per_bbl: amountFor(p.cost_per_bbl),
          })),
        ),
      )
      .catch(() => undefined);

    getMarginTrend(params)
      .then((res) => setMarginRows(res.points.map((p) => ({ month: p.month, margin: amountFor(p.margin) }))))
      .catch(() => undefined);
  }, [facilityId, wellId]);

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader title="Cost & Revenue Trends" description="Revenue, cost, margin, and production-loss impact over time." />

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
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <TrendChart
          title="Production Over Time"
          data={productionRows}
          xKey="record_date"
          showTableToggle
          series={[
            { key: "oil_bopd", label: "Oil", unit: "BOPD", color: "var(--chart-series-1)" },
            { key: "gas_mscfd", label: "Gas", unit: "MSCFD", color: "var(--chart-series-2)" },
          ]}
        />
        <TrendChart
          title="Revenue Over Time"
          data={revenueRows}
          xKey="month"
          showTableToggle
          series={[{ key: "total_revenue", label: "Total Revenue", color: "var(--chart-series-1)" }]}
        />
        <TrendChart
          title="Operating Cost Over Time"
          data={costRows}
          xKey="month"
          showTableToggle
          series={[{ key: "total_cost", label: "Operating Cost", color: "var(--chart-series-2)" }]}
        />
        <TrendChart
          title="Maintenance Cost Over Time"
          data={maintenanceCostRows}
          xKey="month"
          showTableToggle
          series={[{ key: "total_cost", label: "Maintenance Cost", color: "var(--chart-series-3)" }]}
        />
        <TrendChart
          title="Cost per Barrel"
          data={costRows}
          xKey="month"
          series={[{ key: "cost_per_bbl", label: "Cost/bbl", color: "var(--chart-series-2)" }]}
        />
        <TrendChart
          title="Revenue per Barrel"
          data={revenueRows}
          xKey="month"
          series={[{ key: "revenue_per_bbl", label: "Revenue/bbl", color: "var(--chart-series-1)" }]}
        />
        <TrendChart
          title="Estimated Operating Margin"
          data={marginRows}
          xKey="month"
          series={[{ key: "margin", label: "Margin", color: "var(--chart-series-4)" }]}
        />
        <TrendChart
          title="Production-Loss Financial Impact"
          data={lossRows}
          xKey="month"
          series={[{ key: "total_revenue_impact", label: "Estimated Lost Revenue", color: "var(--status-critical)" }]}
        />
      </div>

      <p className="text-xs text-zinc-400 dark:text-zinc-500">
        Maintenance cost and production-loss charts reuse the Maintenance and Production Loss modules&apos; own
        trend endpoints directly — figures are never recomputed here, avoiding double counting. Money series show
        each period&apos;s dominant currency (USD where present).
      </p>
    </div>
  );
}
