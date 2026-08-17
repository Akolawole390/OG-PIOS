"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import {
  deleteProductionLoss,
  getCurrentUser,
  getProductionLoss,
  type CurrentUser,
  type ProductionLossEntry,
} from "@/lib/api";
import { formatCurrency, formatLabel } from "@/lib/format";

const CAN_MANAGE = new Set(["Administrator", "Production Engineer"]);

function formatNumber(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString(undefined, { maximumFractionDigits: digits });
}

export default function ProductionLossDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = Number(params.id);

  const [record, setRecord] = useState<ProductionLossEntry | null>(null);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    getProductionLoss(id).then(setRecord).catch(() => setError("Unable to load this record."));
    getCurrentUser().then(setCurrentUser).catch(() => undefined);
  }, [id]);

  async function handleDelete() {
    if (!window.confirm("Delete this production loss record? Only possible when it isn't linked to a downtime event or maintenance record.")) {
      return;
    }
    setIsDeleting(true);
    try {
      await deleteProductionLoss(id);
      router.push("/production-loss/list");
    } catch {
      setError("Unable to delete — this record is linked to a downtime event or maintenance record. Edit it instead.");
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
          title={`Loss on ${record.loss_date}`}
          description={`${record.category ? formatLabel(record.category) : "Uncategorized"}${scopeLabel ? ` · ${scopeLabel}` : ""}${record.equipment_tag ? ` · ${record.equipment_tag}` : ""}`}
        />
        {canManage ? (
          <div className="flex shrink-0 gap-2">
            <Link
              href={`/production-loss/${record.id}/edit`}
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

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <InfoCard label="Oil Lost" value={record.estimated_bopd_lost !== null ? `${formatNumber(record.estimated_bopd_lost)} bbl` : "—"} calculated />
        <InfoCard label="Gas Lost" value={record.estimated_mscf_lost !== null ? `${formatNumber(record.estimated_mscf_lost)} mscf` : "—"} calculated />
        <InfoCard label="Revenue Impact" value={formatCurrency(record.estimated_revenue_impact, record.currency)} calculated />
        <InfoCard label="Downtime" value={record.downtime_hours !== null ? `${formatNumber(record.downtime_hours)} hrs` : "—"} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Details</h3>
          <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
            <InfoItem label="Category" value={record.category ? formatLabel(record.category) : "—"} />
            <InfoItem label="Well" value={record.well_code ?? "—"} />
            <InfoItem label="Equipment" value={record.equipment_tag ?? "—"} />
            <InfoItem
              label="Maintenance Record"
              value={record.work_order_number ?? (record.maintenance_record_id ? `#${record.maintenance_record_id}` : "—")}
            />
            <InfoItem label="Downtime Event" value={record.downtime_event_id ? `#${record.downtime_event_id}` : "—"} />
          </dl>
          {record.cause ? <p className="mt-3 text-sm text-zinc-600 dark:text-zinc-400">{record.cause}</p> : null}
        </div>

        <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Commodity Pricing Used</h3>
          <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
            <InfoItem label="Oil Price" value={record.oil_price_per_bbl !== null ? `$${formatNumber(record.oil_price_per_bbl, 2)}/bbl` : "—"} />
            <InfoItem label="Gas Price" value={record.gas_price_per_mscf !== null ? `$${formatNumber(record.gas_price_per_mscf, 2)}/mscf` : "—"} />
            <InfoItem label="Currency" value={record.currency ?? "—"} />
          </dl>
          <p className="mt-3 text-xs text-zinc-400 dark:text-zinc-500">{record.disclaimer_text}</p>
        </div>
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
            Estimate
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
