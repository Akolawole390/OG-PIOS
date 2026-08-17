"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { PageHeader } from "@/components/layout/PageHeader";
import { BarChart, type BarDatum } from "@/components/charts/BarChart";
import { TrendChart } from "@/components/charts/TrendChart";
import {
  getMaintenanceByScope,
  getMaintenanceCostTrend,
  getMaintenanceDashboard,
  type MaintenanceDashboard as MaintenanceDashboardType,
} from "@/lib/api";
import { formatLabel } from "@/lib/format";

function formatNumber(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString(undefined, { maximumFractionDigits: digits });
}

export default function MaintenanceDashboardPage() {
  const [dashboard, setDashboard] = useState<MaintenanceDashboardType | null>(null);
  const [statusBars, setStatusBars] = useState<BarDatum[]>([]);
  const [typeBars, setTypeBars] = useState<BarDatum[]>([]);
  const [equipmentBars, setEquipmentBars] = useState<BarDatum[]>([]);
  const [fieldBars, setFieldBars] = useState<BarDatum[]>([]);
  const [downtimeByEquipment, setDowntimeByEquipment] = useState<BarDatum[]>([]);
  const [costTrend, setCostTrend] = useState<Record<string, number | string | null>[]>([]);

  useEffect(() => {
    getMaintenanceDashboard()
      .then((res) => {
        setDashboard(res);
        const counts = res.status_counts;
        setStatusBars(
          (["scheduled", "open", "in_progress", "waiting_for_parts", "completed", "cancelled"] as const).map((key) => ({
            key,
            label: formatLabel(key),
            value: counts[key],
          })),
        );
      })
      .catch(() => undefined);
    getMaintenanceByScope({ group_by: "type" })
      .then((res) => setTypeBars(res.bars.map((b) => ({ key: b.key, label: formatLabel(b.label), value: b.count }))))
      .catch(() => undefined);
    getMaintenanceByScope({ group_by: "equipment" })
      .then((res) => {
        const top = res.bars.slice(0, 8);
        setEquipmentBars(top.map((b) => ({ key: b.key, label: b.label, value: b.count })));
        setDowntimeByEquipment(
          [...top]
            .sort((a, b) => b.total_downtime_hours - a.total_downtime_hours)
            .slice(0, 8)
            .map((b) => ({ key: b.key, label: b.label, value: b.total_downtime_hours })),
        );
      })
      .catch(() => undefined);
    getMaintenanceByScope({ group_by: "field" })
      .then((res) => setFieldBars(res.bars.map((b) => ({ key: b.key, label: b.label, value: b.count }))))
      .catch(() => undefined);
    getMaintenanceCostTrend()
      .then((res) => setCostTrend(res.points.map((p) => ({ month: p.month, total_cost: p.total_cost }))))
      .catch(() => undefined);
  }, []);

  return (
    <div className="flex flex-1 flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <PageHeader title="Maintenance Dashboard" description="Fleet-wide maintenance overview. All demo data is synthetic." />
        <div className="flex shrink-0 gap-2">
          <Link
            href="/maintenance/work-orders"
            className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
          >
            Work Orders
          </Link>
          <Link
            href="/maintenance/schedule"
            className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
          >
            Schedule
          </Link>
          <Link
            href="/maintenance/list"
            className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
          >
            All Records
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard label="Total Activities" value={formatNumber(dashboard?.status_counts.total)} />
        <KpiCard label="Scheduled" value={formatNumber(dashboard?.status_counts.scheduled)} />
        <KpiCard
          label="Overdue"
          value={formatNumber(dashboard?.status_counts.computed_overdue_count)}
          hint="Planned completion date has passed"
          calculated
        />
        <KpiCard label="Open" value={formatNumber(dashboard?.status_counts.open)} />
        <KpiCard label="In Progress" value={formatNumber(dashboard?.status_counts.in_progress)} />
        <KpiCard label="Completed" value={formatNumber(dashboard?.status_counts.completed)} />
        <KpiCard label="Emergency" value={formatNumber(dashboard?.status_counts.emergency_count)} />
        <KpiCard label="Maintenance Cost" value={`$${formatNumber(dashboard?.total_cost, 0)}`} calculated />
        <KpiCard label="Maintenance Downtime" value={`${formatNumber(dashboard?.total_downtime_hours)} hrs`} calculated />
        <KpiCard
          label="Equipment Requiring Maintenance"
          value={formatNumber(dashboard?.equipment_requiring_maintenance.length)}
          hint="Next maintenance date due or overdue"
          calculated
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <BarChart title="Work Orders by Status" data={statusBars} unit="items" />
        <BarChart title="Maintenance by Type" data={typeBars} unit="items" />
        <BarChart title="Maintenance by Equipment (Top 8)" data={equipmentBars} unit="items" />
        <BarChart title="Maintenance by Field" data={fieldBars} unit="items" />
        <BarChart title="Downtime by Equipment (Top 8)" data={downtimeByEquipment} unit="hrs" />
        <TrendChart
          title="Maintenance Cost Over Time"
          data={costTrend}
          xKey="month"
          showTableToggle
          series={[{ key: "total_cost", label: "Cost", unit: "$", color: "var(--chart-series-1)" }]}
        />
      </div>

      <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Equipment Requiring Maintenance</h3>
        <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
          Rule-based — next maintenance date is due or overdue, not a failure prediction.
        </p>
        {dashboard && dashboard.equipment_requiring_maintenance.length > 0 ? (
          <ul className="mt-3 space-y-2 text-sm">
            {dashboard.equipment_requiring_maintenance.map((item) => (
              <li key={item.equipment_id} className="flex items-center justify-between gap-3 border-b border-zinc-100 pb-2 last:border-0 dark:border-zinc-900">
                <Link href={`/equipment/${item.equipment_id}`} className="font-medium text-zinc-900 hover:underline dark:text-zinc-50">
                  {item.equipment_tag} — {item.equipment_name}
                </Link>
                <span className="shrink-0 text-xs text-zinc-500 dark:text-zinc-400">
                  {item.days_from_today < 0
                    ? `${Math.abs(item.days_from_today)} day(s) overdue`
                    : item.days_from_today === 0
                      ? "Due today"
                      : `Due in ${item.days_from_today} day(s)`}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-sm text-zinc-500 dark:text-zinc-400">None.</p>
        )}
      </div>
    </div>
  );
}
