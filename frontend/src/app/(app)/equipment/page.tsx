"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { PageHeader } from "@/components/layout/PageHeader";
import { BarChart, type BarDatum } from "@/components/charts/BarChart";
import { HealthDistributionChart } from "@/components/charts/HealthDistributionChart";
import {
  getEquipmentByScope,
  getEquipmentDashboard,
  getEquipmentIssues,
  type EquipmentDashboard as EquipmentDashboardType,
  type EquipmentIssuesResponse,
} from "@/lib/api";
import { formatLabel } from "@/lib/format";

function formatNumber(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString(undefined, { maximumFractionDigits: digits });
}

export default function EquipmentDashboardPage() {
  const [dashboard, setDashboard] = useState<EquipmentDashboardType | null>(null);
  const [byType, setByType] = useState<BarDatum[]>([]);
  const [byField, setByField] = useState<BarDatum[]>([]);
  const [byFacility, setByFacility] = useState<BarDatum[]>([]);
  const [issues, setIssues] = useState<EquipmentIssuesResponse | null>(null);

  useEffect(() => {
    getEquipmentDashboard().then(setDashboard).catch(() => undefined);
    getEquipmentByScope({ group_by: "type" })
      .then((res) => setByType(res.bars.map((b) => ({ key: b.key, label: formatLabel(b.label), value: b.count }))))
      .catch(() => undefined);
    getEquipmentByScope({ group_by: "field" })
      .then((res) => setByField(res.bars.map((b) => ({ key: b.key, label: b.label, value: b.count }))))
      .catch(() => undefined);
    getEquipmentByScope({ group_by: "facility" })
      .then((res) => setByFacility(res.bars.map((b) => ({ key: b.key, label: b.label, value: b.count }))))
      .catch(() => undefined);
    getEquipmentIssues({ limit: 10 }).then(setIssues).catch(() => undefined);
  }, []);

  return (
    <div className="flex flex-1 flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <PageHeader title="Equipment Dashboard" description="Fleet-wide equipment status and health overview. All demo data is synthetic." />
        <Link
          href="/equipment/list"
          className="shrink-0 rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
        >
          View Equipment List
        </Link>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <KpiCard label="Total Equipment" value={formatNumber(dashboard?.status_counts.total)} />
        <KpiCard label="Operating" value={formatNumber(dashboard?.status_counts.operating)} />
        <KpiCard label="In Maintenance" value={formatNumber(dashboard?.status_counts.maintenance)} />
        <KpiCard label="Failed" value={formatNumber(dashboard?.status_counts.failed)} />
        <KpiCard
          label="Requires Attention"
          value={formatNumber(dashboard?.status_counts.attention_count)}
          hint="Failed, or health score in Maintenance Required/Critical bands"
          calculated
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <HealthDistributionChart
          title="Health Score Distribution"
          buckets={dashboard?.health_distribution.buckets ?? []}
          unscoredCount={dashboard?.health_distribution.unscored_count}
        />
        <BarChart title="Equipment by Type" data={byType} unit="items" />
        <BarChart title="Equipment by Field" data={byField} unit="items" />
        <BarChart title="Equipment by Facility" data={byFacility} unit="items" />
      </div>

      <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Equipment Requiring Investigation</h3>
        <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
          Failed status first, then lowest health score. Rule-based ranking — not a failure prediction; requires
          engineering review.
        </p>
        {issues && issues.items.length > 0 ? (
          <ul className="mt-3 space-y-2 text-sm">
            {issues.items.map((item) => (
              <li
                key={item.id}
                className="flex items-center justify-between gap-3 border-b border-zinc-100 pb-2 last:border-0 dark:border-zinc-900"
              >
                <div>
                  <Link href={`/equipment/${item.id}`} className="font-medium text-zinc-900 hover:underline dark:text-zinc-50">
                    {item.equipment_tag} — {item.name}
                  </Link>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400">{item.detail}</p>
                </div>
                <span className="shrink-0 text-xs font-medium text-zinc-700 dark:text-zinc-300">
                  {item.health_score !== null ? `${item.health_score.toFixed(0)} (${item.health_band})` : formatLabel(item.status)}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-sm text-zinc-500 dark:text-zinc-400">No equipment currently requires investigation.</p>
        )}
      </div>
    </div>
  );
}
