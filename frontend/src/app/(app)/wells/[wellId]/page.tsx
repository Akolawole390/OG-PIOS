"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { PageHeader } from "@/components/layout/PageHeader";
import { TrendChart } from "@/components/charts/TrendChart";
import {
  getWell,
  getWellDowntime,
  getWellMaintenance,
  getWellPressure,
  getWellProduction,
  type DowntimeResponse,
  type MaintenanceResponse,
  type PressureRecord,
  type ProductionRecord,
  type Well,
} from "@/lib/api";
import { formatLabel } from "@/lib/format";

function formatNumber(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString(undefined, { maximumFractionDigits: digits });
}

function formatDateTime(value: string | null): string {
  if (!value) return "Ongoing";
  return new Date(value).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export default function WellDetailPage() {
  const params = useParams<{ wellId: string }>();
  const id = Number(params.wellId);

  const [well, setWell] = useState<Well | null>(null);
  const [production, setProduction] = useState<ProductionRecord[]>([]);
  const [pressure, setPressure] = useState<PressureRecord[]>([]);
  const [downtime, setDowntime] = useState<DowntimeResponse | null>(null);
  const [maintenance, setMaintenance] = useState<MaintenanceResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      getWell(id),
      getWellProduction(id, 90),
      getWellPressure(id, 90),
      getWellDowntime(id),
      getWellMaintenance(id),
    ])
      .then(([wellData, productionData, pressureData, downtimeData, maintenanceData]) => {
        setWell(wellData);
        setProduction(productionData);
        setPressure(pressureData);
        setDowntime(downtimeData);
        setMaintenance(maintenanceData);
      })
      .catch(() => setError("Unable to load this well."));
  }, [id]);

  if (error) {
    return <p className="text-sm text-red-600 dark:text-red-400">{error}</p>;
  }

  if (!well) {
    return <p className="text-sm text-zinc-500 dark:text-zinc-400">Loading…</p>;
  }

  const latest = production.length > 0 ? production[production.length - 1] : null;

  return (
    <div className="flex flex-1 flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <PageHeader title={well.name} description={`${well.well_id} — ${well.facility.name}, ${well.facility.field.name}`} />
        <Link
          href={`/wells/${well.id}/edit`}
          className="shrink-0 rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
        >
          Edit
        </Link>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard label="Oil Production" value={formatNumber(latest?.oil_bopd)} unit="BOPD" />
        <KpiCard label="Gas Production" value={formatNumber(latest?.gas_mscfd)} unit="MSCFD" />
        <KpiCard label="Water Production" value={formatNumber(latest?.water_bwpd)} unit="BWPD" />
        <KpiCard label="Water Cut" value={formatNumber(latest?.water_cut_pct)} unit="%" />
      </div>

      <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Well Information</h3>
        <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3 lg:grid-cols-4">
          <InfoItem label="Status" value={formatLabel(well.status)} />
          <InfoItem label="Type" value={well.well_type ? formatLabel(well.well_type) : "—"} />
          <InfoItem label="Artificial Lift" value={well.artificial_lift_type ? formatLabel(well.artificial_lift_type) : "—"} />
          <InfoItem
            label="Location"
            value={well.latitude !== null && well.longitude !== null ? `${well.latitude}, ${well.longitude}` : "—"}
          />
          <InfoItem label="Completion Date" value={well.completion_date ?? "—"} />
          <InfoItem label="Completion Type" value={well.completion_type ? formatLabel(well.completion_type) : "—"} />
          <InfoItem label="Total Depth" value={well.total_depth_ft ? `${formatNumber(well.total_depth_ft)} ft` : "—"} />
        </dl>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <TrendChart
          title="Production Trend"
          data={production}
          xKey="record_date"
          showTableToggle
          series={[
            { key: "oil_bopd", label: "Oil", unit: "BOPD", color: "var(--chart-series-1)" },
            { key: "gas_mscfd", label: "Gas", unit: "MSCFD", color: "var(--chart-series-2)" },
            { key: "water_bwpd", label: "Water", unit: "BWPD", color: "var(--chart-series-3)" },
          ]}
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
        <TrendChart
          title="Water-Cut Trend"
          data={production}
          xKey="record_date"
          series={[{ key: "water_cut_pct", label: "Water Cut", unit: "%", color: "var(--chart-series-1)" }]}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Downtime Summary</h3>
            <span className="text-xs text-zinc-500 dark:text-zinc-400">
              {downtime?.summary.event_count ?? 0} event{downtime?.summary.event_count === 1 ? "" : "s"} ·{" "}
              {formatNumber(downtime?.summary.total_hours ?? 0)} hrs total
            </span>
          </div>
          {downtime && downtime.events.length > 0 ? (
            <ul className="mt-3 space-y-2 text-sm">
              {downtime.events.map((event) => (
                <li key={event.id} className="border-b border-zinc-100 pb-2 last:border-0 dark:border-zinc-900">
                  <p className="font-medium text-zinc-900 dark:text-zinc-50">{event.reason ?? "Unspecified"}</p>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400">
                    {formatDateTime(event.start_time)} → {formatDateTime(event.end_time)}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-zinc-500 dark:text-zinc-400">No downtime recorded.</p>
          )}
        </div>

        <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Maintenance Summary</h3>
            <span className="text-xs text-zinc-500 dark:text-zinc-400">
              {maintenance?.summary.record_count ?? 0} record{maintenance?.summary.record_count === 1 ? "" : "s"} · $
              {formatNumber(maintenance?.summary.total_cost ?? 0, 0)} total
            </span>
          </div>
          {maintenance && maintenance.records.length > 0 ? (
            <ul className="mt-3 space-y-2 text-sm">
              {maintenance.records.map((record) => (
                <li key={record.id} className="border-b border-zinc-100 pb-2 last:border-0 dark:border-zinc-900">
                  <p className="font-medium text-zinc-900 dark:text-zinc-50">
                    {formatLabel(record.maintenance_type)} — {record.equipment_tag}
                  </p>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400">
                    {formatLabel(record.status)} · {record.start_date ?? "—"}
                    {record.cost ? ` · $${formatNumber(record.cost, 0)}` : ""}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-zinc-500 dark:text-zinc-400">No maintenance recorded.</p>
          )}
        </div>
      </div>
    </div>
  );
}

function InfoItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">{label}</dt>
      <dd className="mt-0.5 text-zinc-900 dark:text-zinc-50">{value}</dd>
    </div>
  );
}
