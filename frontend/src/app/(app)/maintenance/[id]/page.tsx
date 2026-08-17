"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { MaintenancePriorityBadge, MaintenanceStatusBadge } from "@/components/maintenance/MaintenanceTable";
import {
  deleteMaintenance,
  getCurrentUser,
  getMaintenance,
  type CurrentUser,
  type MaintenanceEntry,
} from "@/lib/api";
import { formatLabel } from "@/lib/format";

const CAN_MANAGE = new Set(["Administrator", "Maintenance Engineer"]);

function formatNumber(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString(undefined, { maximumFractionDigits: digits });
}

export default function MaintenanceDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = Number(params.id);

  const [record, setRecord] = useState<MaintenanceEntry | null>(null);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    getMaintenance(id).then(setRecord).catch(() => setError("Unable to load this work order."));
    getCurrentUser().then(setCurrentUser).catch(() => undefined);
  }, [id]);

  async function handleDelete() {
    if (!window.confirm("Delete this work order? Only possible while scheduled/open with no recorded cost or downtime.")) {
      return;
    }
    setIsDeleting(true);
    try {
      await deleteMaintenance(id);
      router.push("/maintenance/list");
    } catch {
      setError("Unable to delete — this work order has recorded status/cost/downtime. Cancel it instead via Edit.");
      setIsDeleting(false);
    }
  }

  if (error && !record) return <p className="text-sm text-red-600 dark:text-red-400">{error}</p>;
  if (!record) return <p className="text-sm text-zinc-500 dark:text-zinc-400">Loading…</p>;

  const canManage = currentUser ? CAN_MANAGE.has(currentUser.role_name) : false;
  const scopeLabel = [record.field_name, record.facility_name, record.well_code].filter(Boolean).join(" / ");

  return (
    <div className="flex flex-1 flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <PageHeader
          title={record.work_order_number ?? `Work Order #${record.id}`}
          description={`${formatLabel(record.maintenance_type)} — ${record.equipment_tag}${scopeLabel ? ` · ${scopeLabel}` : ""}`}
        />
        {canManage ? (
          <div className="flex shrink-0 gap-2">
            <Link
              href={`/maintenance/${record.id}/edit`}
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

      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

      <div className="flex flex-wrap items-center gap-2">
        <MaintenancePriorityBadge priority={record.priority} />
        <MaintenanceStatusBadge status={record.status} />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <InfoCard label="Equipment" value={record.equipment_tag} />
        <InfoCard label="Technician" value={record.technician_name ?? "Unassigned"} />
        <InfoCard label="Total Cost" value={record.cost !== null ? `$${formatNumber(record.cost, 2)}` : "—"} calculated />
        <InfoCard label="Downtime" value={record.downtime_hours !== null ? `${formatNumber(record.downtime_hours)} hrs` : "—"} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Scheduling</h3>
          <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
            <InfoItem label="Planned Start" value={record.planned_start_date ?? "—"} />
            <InfoItem label="Planned Completion" value={record.planned_completion_date ?? "—"} />
            <InfoItem label="Actual Start" value={record.start_date ?? "—"} />
            <InfoItem label="Actual Completion" value={record.completion_date ?? "—"} />
          </dl>
        </div>

        <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Cost Breakdown</h3>
          <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
            <InfoItem label="Labor" value={record.labor_cost !== null ? `$${formatNumber(record.labor_cost, 2)}` : "—"} />
            <InfoItem label="Parts" value={record.parts_cost !== null ? `$${formatNumber(record.parts_cost, 2)}` : "—"} />
            <InfoItem label="Contractor" value={record.contractor_cost !== null ? `$${formatNumber(record.contractor_cost, 2)}` : "—"} />
            <InfoItem label="Other" value={record.other_cost !== null ? `$${formatNumber(record.other_cost, 2)}` : "—"} />
          </dl>
        </div>
      </div>

      <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Details</h3>
        <dl className="mt-3 grid grid-cols-1 gap-3 text-sm">
          <InfoItem label="Description" value={record.description ?? "—"} />
          <InfoItem label="Failure Cause" value={record.failure_cause ?? "—"} />
          <InfoItem label="Corrective Action" value={record.corrective_action ?? "—"} />
          <InfoItem label="Notes" value={record.notes ?? "—"} />
        </dl>
      </div>
    </div>
  );
}

function InfoCard({ label, value, calculated }: { label: string; value: string; calculated?: boolean }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex items-center gap-1.5">
        <p className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">{label}</p>
        {calculated ? (
          <span className="rounded border border-zinc-300 px-1 text-[10px] font-medium uppercase tracking-wide text-zinc-400 dark:border-zinc-700 dark:text-zinc-500">
            Calculated
          </span>
        ) : null}
      </div>
      <p className="mt-2 text-lg font-semibold text-zinc-900 dark:text-zinc-50">{value}</p>
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
