"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { PageHeader } from "@/components/layout/PageHeader";
import { TrendChart } from "@/components/charts/TrendChart";
import { EquipmentHealthBreakdown } from "@/components/equipment/EquipmentHealthBreakdown";
import {
  deleteEquipment,
  getCurrentUser,
  getEquipment,
  getEquipmentDowntime,
  getEquipmentHealth,
  getEquipmentMaintenance,
  getEquipmentReliability,
  listEquipmentReadings,
  listProductionLoss,
  type CurrentUser,
  type DowntimeResponse,
  type Equipment,
  type EquipmentHealth,
  type EquipmentReading,
  type MaintenanceResponse,
  type ProductionLossEntry,
  type ReliabilityMetrics,
} from "@/lib/api";
import { formatCurrency, formatLabel } from "@/lib/format";

const CAN_MANAGE = new Set(["Administrator", "Maintenance Engineer"]);

const READING_PARAMETERS: { key: string; label: string; color: string }[] = [
  { key: "temperature", label: "Temperature", color: "var(--chart-series-1)" },
  { key: "vibration", label: "Vibration", color: "var(--chart-series-2)" },
  { key: "current", label: "Current", color: "var(--chart-series-3)" },
  { key: "flow", label: "Flow", color: "var(--chart-series-4)" },
];

function formatNumber(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString(undefined, { maximumFractionDigits: digits });
}

function formatDateTime(value: string | null): string {
  if (!value) return "Ongoing";
  return new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export default function EquipmentDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = Number(params.id);

  const [equipment, setEquipment] = useState<Equipment | null>(null);
  const [health, setHealth] = useState<EquipmentHealth | null>(null);
  const [downtime, setDowntime] = useState<DowntimeResponse | null>(null);
  const [maintenance, setMaintenance] = useState<MaintenanceResponse | null>(null);
  const [reliability, setReliability] = useState<ReliabilityMetrics | null>(null);
  const [productionLoss, setProductionLoss] = useState<ProductionLossEntry[]>([]);
  const [readingsByParameter, setReadingsByParameter] = useState<Record<string, EquipmentReading[]>>({});
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    getCurrentUser().then(setCurrentUser).catch(() => undefined);

    Promise.all([
      getEquipment(id),
      getEquipmentHealth(id),
      getEquipmentDowntime(id),
      getEquipmentMaintenance(id),
      getEquipmentReliability(id),
      listProductionLoss({ equipment_id: id, page_size: 10, sort: "loss_date", order: "desc" }),
      ...READING_PARAMETERS.map((p) => listEquipmentReadings(id, { parameter: p.key, page_size: 200 })),
    ])
      .then(([equipmentData, healthData, downtimeData, maintenanceData, reliabilityData, productionLossData, ...readingResponses]) => {
        setEquipment(equipmentData);
        setHealth(healthData);
        setDowntime(downtimeData);
        setMaintenance(maintenanceData);
        setReliability(reliabilityData);
        setProductionLoss(productionLossData.items);
        const grouped: Record<string, EquipmentReading[]> = {};
        READING_PARAMETERS.forEach((p, index) => {
          grouped[p.key] = readingResponses[index].items;
        });
        setReadingsByParameter(grouped);
      })
      .catch(() => setError("Unable to load this equipment record."));
  }, [id]);

  async function handleDelete() {
    if (!window.confirm("Delete this equipment record? This is only allowed if it has no maintenance, reading, or downtime history.")) {
      return;
    }
    setIsDeleting(true);
    try {
      await deleteEquipment(id);
      router.push("/equipment/list");
    } catch {
      setError("Unable to delete this equipment record — it may still have associated history.");
      setIsDeleting(false);
    }
  }

  if (error) return <p className="text-sm text-red-600 dark:text-red-400">{error}</p>;
  if (!equipment) return <p className="text-sm text-zinc-500 dark:text-zinc-400">Loading…</p>;

  const canManage = currentUser ? CAN_MANAGE.has(currentUser.role_name) : false;
  const scopeLabel = [equipment.field_name, equipment.facility_name, equipment.well_code].filter(Boolean).join(" / ");

  return (
    <div className="flex flex-1 flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <PageHeader
          title={equipment.name}
          description={`${equipment.equipment_tag} — ${formatLabel(equipment.equipment_type)}${scopeLabel ? ` · ${scopeLabel}` : ""}`}
        />
        {canManage ? (
          <div className="flex shrink-0 gap-2">
            <Link
              href={`/equipment/${equipment.id}/edit`}
              className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
            >
              Edit
            </Link>
            <button
              type="button"
              onClick={handleDelete}
              disabled={isDeleting}
              className="rounded-md border border-red-300 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50 dark:border-red-900 dark:text-red-400 dark:hover:bg-red-950/40"
            >
              {isDeleting ? "Deleting…" : "Delete"}
            </button>
          </div>
        ) : null}
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard label="Status" value={formatLabel(equipment.status)} />
        <KpiCard label="Operating Hours" value={formatNumber(equipment.operating_hours, 0)} unit="hrs" />
        <KpiCard label="Health Score" value={equipment.health_score !== null ? equipment.health_score.toFixed(0) : "—"} hint={equipment.health_band ?? undefined} calculated />
        <KpiCard label="Last Maintenance" value={equipment.last_maintenance_date ?? "—"} calculated />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Equipment Information</h3>
          <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
            <InfoItem label="Manufacturer" value={equipment.manufacturer ?? "—"} />
            <InfoItem label="Model" value={equipment.model ?? "—"} />
            <InfoItem label="Serial Number" value={equipment.serial_number ?? "—"} />
            <InfoItem label="Installation Date" value={equipment.installation_date ?? "—"} />
            <InfoItem label="Commissioning Date" value={equipment.commissioning_date ?? "—"} />
            <InfoItem label="Next Maintenance Due" value={equipment.next_maintenance_due ?? "—"} />
          </dl>
          {equipment.description ? (
            <p className="mt-3 text-sm text-zinc-600 dark:text-zinc-400">{equipment.description}</p>
          ) : null}
        </div>

        <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Associated Assets</h3>
          <dl className="mt-3 grid grid-cols-1 gap-3 text-sm sm:grid-cols-3">
            <InfoItem label="Field" value={equipment.field_name ?? "—"} />
            <InfoItem label="Facility" value={equipment.facility_name ?? "—"} />
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">Well</dt>
              <dd className="mt-0.5 text-zinc-900 dark:text-zinc-50">
                {equipment.well_id && equipment.well_code ? (
                  <Link href={`/wells/${equipment.well_id}`} className="hover:underline">
                    {equipment.well_code}
                  </Link>
                ) : (
                  "—"
                )}
              </dd>
            </div>
          </dl>
          {!equipment.well_id && !equipment.facility_id ? (
            <p className="mt-3 text-xs text-zinc-500 dark:text-zinc-400">
              This equipment is not associated with a well or facility.
            </p>
          ) : null}
        </div>
      </div>

      <EquipmentHealthBreakdown health={health} />

      <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Reliability (Foundation)</h3>
        {reliability ? (
          <>
            <div className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-4">
              <ReliabilityStat
                label="MTBF"
                value={reliability.mtbf_data_sufficient ? `${formatNumber(reliability.mtbf_hours)} hrs` : "Insufficient data"}
              />
              <ReliabilityStat
                label="MTTR"
                value={reliability.mttr_data_sufficient ? `${formatNumber(reliability.mttr_hours)} hrs` : "Insufficient data"}
              />
              <ReliabilityStat
                label="Availability"
                value={reliability.availability_pct !== null ? `${formatNumber(reliability.availability_pct)}%` : "—"}
              />
              <ReliabilityStat label="Failures Recorded" value={String(reliability.failure_count)} />
            </div>
            <p className="mt-3 text-xs text-zinc-400 dark:text-zinc-500">{reliability.disclaimer_text}</p>
          </>
        ) : (
          <p className="mt-3 text-sm text-zinc-500 dark:text-zinc-400">Loading…</p>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {READING_PARAMETERS.map((p) => {
          const readings = readingsByParameter[p.key] ?? [];
          if (readings.length === 0) return null;
          const rows = readings.map((r) => ({ reading_at: r.reading_at, value: r.value }));
          return (
            <TrendChart
              key={p.key}
              title={`${p.label} Trend`}
              data={rows}
              xKey="reading_at"
              showTableToggle
              series={[{ key: "value", label: p.label, unit: readings[0]?.unit ?? undefined, color: p.color }]}
            />
          );
        })}
        {READING_PARAMETERS.every((p) => (readingsByParameter[p.key] ?? []).length === 0) ? (
          <p className="text-sm text-zinc-500 dark:text-zinc-400 lg:col-span-2">
            No sensor readings recorded for this equipment yet.
          </p>
        ) : null}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Maintenance History</h3>
            {canManage ? (
              <Link
                href={`/maintenance/new?equipment_id=${equipment.id}`}
                className="text-xs font-medium text-zinc-500 underline-offset-2 hover:text-zinc-900 hover:underline dark:text-zinc-400 dark:hover:text-zinc-50"
              >
                + Add Work Order
              </Link>
            ) : null}
          </div>
          <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
            {maintenance?.summary.record_count ?? 0} record{maintenance?.summary.record_count === 1 ? "" : "s"} · $
            {formatNumber(maintenance?.summary.total_cost ?? 0, 0)} total cost ·{" "}
            {formatNumber(maintenance?.summary.total_downtime_hours ?? 0)} hrs total downtime
          </p>
          {maintenance && maintenance.records.length > 0 ? (
            <ul className="mt-3 space-y-2 text-sm">
              {maintenance.records.map((record) => (
                <li key={record.id} className="border-b border-zinc-100 pb-2 last:border-0 dark:border-zinc-900">
                  <Link href={`/maintenance/${record.id}`} className="font-medium text-zinc-900 hover:underline dark:text-zinc-50">
                    {formatLabel(record.maintenance_type)}
                  </Link>
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

        <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Failure / Downtime History</h3>
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
      </div>

      <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Production Loss Events</h3>
          {canManage ? (
            <Link
              href={`/production-loss/new?equipment_id=${equipment.id}`}
              className="text-xs font-medium text-zinc-500 underline-offset-2 hover:text-zinc-900 hover:underline dark:text-zinc-400 dark:hover:text-zinc-50"
            >
              + Add Loss Record
            </Link>
          ) : null}
        </div>
        <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
          Estimated production loss and financial impact attributed to this equipment — see each record for its
          disclaimer.
        </p>
        {productionLoss.length > 0 ? (
          <ul className="mt-3 space-y-2 text-sm">
            {productionLoss.map((loss) => (
              <li key={loss.id} className="flex items-center justify-between gap-3 border-b border-zinc-100 pb-2 last:border-0 dark:border-zinc-900">
                <div>
                  <Link href={`/production-loss/${loss.id}`} className="font-medium text-zinc-900 hover:underline dark:text-zinc-50">
                    {loss.loss_date}
                  </Link>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400">
                    {loss.category ? formatLabel(loss.category) : "Uncategorized"}
                    {loss.estimated_bopd_lost !== null ? ` · ${formatNumber(loss.estimated_bopd_lost)} bbl oil lost` : ""}
                  </p>
                </div>
                <span className="shrink-0 text-xs font-medium text-zinc-700 dark:text-zinc-300">
                  {formatCurrency(loss.estimated_revenue_impact, loss.currency)}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-sm text-zinc-500 dark:text-zinc-400">No production loss recorded for this equipment.</p>
        )}
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

function ReliabilityStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">{label}</p>
      <p className="mt-0.5 text-lg font-semibold text-zinc-900 dark:text-zinc-50">{value}</p>
    </div>
  );
}
