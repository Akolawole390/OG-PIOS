"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { formatCurrency } from "@/lib/format";
import {
  deleteOperatingCost,
  getCurrentUser,
  getOperatingCost,
  type CurrentUser,
  type OperatingCostEntry,
} from "@/lib/api";

const CAN_MANAGE = new Set(["Administrator", "Management"]);

export default function OperatingCostDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = Number(params.id);

  const [record, setRecord] = useState<OperatingCostEntry | null>(null);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    getOperatingCost(id).then(setRecord).catch(() => setError("Unable to load this record."));
    getCurrentUser().then(setCurrentUser).catch(() => undefined);
  }, [id]);

  async function handleDelete() {
    if (!window.confirm("Delete this operating cost record?")) return;
    setIsDeleting(true);
    try {
      await deleteOperatingCost(id);
      router.push("/cost-revenue/operating-costs");
    } catch {
      setError("Unable to delete this record.");
      setIsDeleting(false);
    }
  }

  if (error && !record) return <p className="text-sm text-red-600 dark:text-red-400">{error}</p>;
  if (!record) return <p className="text-sm text-zinc-500 dark:text-zinc-400">Loading…</p>;

  const canManage = currentUser ? CAN_MANAGE.has(currentUser.role_name) : false;
  const scopeLabel = [record.field_name, record.facility_name, record.well_code, record.equipment_tag].filter(Boolean).join(" / ");

  return (
    <div className="flex flex-1 flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <PageHeader title={`${record.category} — ${record.cost_date}`} description={scopeLabel || "No specific scope"} />
        {canManage ? (
          <div className="flex shrink-0 gap-2">
            <Link href={`/cost-revenue/operating-costs/${record.id}/edit`} className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900">
              Edit
            </Link>
            <button type="button" onClick={handleDelete} disabled={isDeleting} className="rounded-md border border-red-300 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50 dark:border-red-900 dark:text-red-400 dark:hover:bg-red-950/40">
              {isDeleting ? "Deleting…" : "Delete"}
            </button>
          </div>
        ) : null}
      </div>

      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <InfoCard label="Amount" value={formatCurrency(record.amount, record.currency)} />
        <InfoCard label="Category" value={record.category} />
        <InfoCard label="Cost Period" value={record.cost_period ?? "—"} />
        <InfoCard label="Source" value={record.source ?? "—"} />
      </div>

      <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Details</h3>
        <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
          <InfoItem label="Field" value={record.field_name ?? "—"} />
          <InfoItem label="Facility" value={record.facility_name ?? "—"} />
          <InfoItem label="Well" value={record.well_code ?? "—"} />
          <InfoItem label="Equipment" value={record.equipment_tag ?? "—"} />
        </dl>
        {record.description ? <p className="mt-3 text-sm text-zinc-600 dark:text-zinc-400">{record.description}</p> : null}
        {record.notes ? <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">{record.notes}</p> : null}
      </div>
    </div>
  );
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <p className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">{label}</p>
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
