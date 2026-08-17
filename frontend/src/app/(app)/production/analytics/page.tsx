"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { BarChart, type BarDatum } from "@/components/charts/BarChart";
import { TrendChart } from "@/components/charts/TrendChart";
import {
  getActualVsTarget,
  getProductionByScope,
  getProductionTrends,
  listFacilities,
  listWells,
  type ActualVsTargetPoint,
  type Facility,
  type Well,
} from "@/lib/api";

export default function ProductionAnalyticsPage() {
  const [wellId, setWellId] = useState("");
  const [facilityId, setFacilityId] = useState("");
  const [fieldId, setFieldId] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [groupBy, setGroupBy] = useState<"well" | "field" | "facility">("well");

  const [wells, setWells] = useState<Well[]>([]);
  const [facilities, setFacilities] = useState<Facility[]>([]);

  const [oilGasWater, setOilGasWater] = useState<Record<string, number | string | null>[]>([]);
  const [waterCut, setWaterCut] = useState<Record<string, number | string | null>[]>([]);
  const [gor, setGor] = useState<Record<string, number | string | null>[]>([]);
  const [pressure, setPressure] = useState<Record<string, number | string | null>[]>([]);
  const [actualVsTarget, setActualVsTarget] = useState<ActualVsTargetPoint[]>([]);
  const [byScope, setByScope] = useState<BarDatum[]>([]);

  useEffect(() => {
    listWells({ page_size: 100, sort: "well_id" }).then((res) => setWells(res.items)).catch(() => undefined);
    listFacilities().then(setFacilities).catch(() => undefined);
  }, []);

  const fields = Array.from(new Map(facilities.map((f) => [f.field_id, f.field_name])).entries());

  useEffect(() => {
    const scope = {
      well_id: wellId ? Number(wellId) : undefined,
      field_id: fieldId ? Number(fieldId) : undefined,
      facility_id: facilityId ? Number(facilityId) : undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
    };

    getProductionTrends("oil_gas_water", scope).then((r) => setOilGasWater(r.points)).catch(() => undefined);
    getProductionTrends("water_cut", scope).then((r) => setWaterCut(r.points)).catch(() => undefined);
    getProductionTrends("gor", scope).then((r) => setGor(r.points)).catch(() => undefined);
    getProductionTrends("pressure", scope).then((r) => setPressure(r.points)).catch(() => undefined);
    getActualVsTarget(scope).then((r) => setActualVsTarget(r.points)).catch(() => undefined);
  }, [wellId, fieldId, facilityId, dateFrom, dateTo]);

  useEffect(() => {
    getProductionByScope({ group_by: groupBy, date_from: dateFrom || undefined, date_to: dateTo || undefined, limit: 15 })
      .then((res) => setByScope(res.bars.map((b) => ({ key: b.key, label: b.label, value: b.oil_bopd }))))
      .catch(() => undefined);
  }, [groupBy, dateFrom, dateTo]);

  const actualVsTargetRows = actualVsTarget.map((p) => ({
    record_date: p.record_date,
    actual_oil_bopd: p.actual_oil_bopd,
    target_oil_bopd: p.target_oil_bopd,
  }));

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader title="Production Analytics" description="Trends and comparisons across wells, fields, and facilities." />

      <div className="flex flex-wrap items-center gap-3">
        <select value={wellId} onChange={(e) => setWellId(e.target.value)} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          <option value="">All wells</option>
          {wells.map((w) => (
            <option key={w.id} value={w.id}>{w.well_id}</option>
          ))}
        </select>
        <select value={fieldId} onChange={(e) => setFieldId(e.target.value)} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          <option value="">All fields</option>
          {fields.map(([id, name]) => (
            <option key={id} value={id}>{name}</option>
          ))}
        </select>
        <select value={facilityId} onChange={(e) => setFacilityId(e.target.value)} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          <option value="">All facilities</option>
          {facilities.map((f) => (
            <option key={f.id} value={f.id}>{f.name}</option>
          ))}
        </select>
        <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900" />
        <span className="text-sm text-zinc-400">to</span>
        <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900" />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <TrendChart
          title="Production Trend"
          data={oilGasWater}
          xKey="record_date"
          showTableToggle
          series={[
            { key: "oil_bopd", label: "Oil", unit: "BOPD", color: "var(--chart-series-1)" },
            { key: "gas_mscfd", label: "Gas", unit: "MSCFD", color: "var(--chart-series-2)" },
            { key: "water_bwpd", label: "Water", unit: "BWPD", color: "var(--chart-series-3)" },
          ]}
        />
        <TrendChart
          title="Actual vs Target (Oil)"
          data={actualVsTargetRows}
          xKey="record_date"
          showTableToggle
          series={[
            { key: "actual_oil_bopd", label: "Actual", unit: "BOPD", color: "var(--chart-series-1)" },
            { key: "target_oil_bopd", label: "Target", unit: "BOPD", color: "var(--chart-series-2)" },
          ]}
        />
        <TrendChart
          title="Water-Cut Trend"
          data={waterCut}
          xKey="record_date"
          series={[{ key: "water_cut_pct", label: "Water Cut", unit: "%", color: "var(--chart-series-1)" }]}
        />
        <TrendChart
          title="GOR Trend"
          data={gor}
          xKey="record_date"
          series={[{ key: "gor", label: "GOR", unit: "scf/bbl", color: "var(--chart-series-1)" }]}
        />
        <TrendChart
          title="Pressure Trend"
          data={pressure}
          xKey="record_date"
          showTableToggle
          series={[
            { key: "wellhead_pressure", label: "Wellhead", unit: "psi", color: "var(--chart-series-1)" },
            { key: "tubing_pressure", label: "Tubing", unit: "psi", color: "var(--chart-series-2)" },
            { key: "casing_pressure", label: "Casing", unit: "psi", color: "var(--chart-series-3)" },
            { key: "flowline_pressure", label: "Flowline", unit: "psi", color: "var(--chart-series-4)" },
          ]}
        />

        <div className="flex flex-col gap-2">
          <select
            value={groupBy}
            onChange={(e) => setGroupBy(e.target.value as "well" | "field" | "facility")}
            className="w-fit rounded-md border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900"
          >
            <option value="well">Group by Well</option>
            <option value="field">Group by Field</option>
            <option value="facility">Group by Facility</option>
          </select>
          <BarChart
            title={`Production by ${groupBy === "well" ? "Well" : groupBy === "field" ? "Field" : "Facility"} (Oil, BOPD)`}
            data={byScope}
            unit="BOPD"
          />
        </div>
      </div>
    </div>
  );
}
