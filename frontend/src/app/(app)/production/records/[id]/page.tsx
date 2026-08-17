"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import {
  deleteProduction,
  getCurrentUser,
  getProduction,
  type CurrentUser,
  type ProductionEntry,
} from "@/lib/api";

const CAN_MANAGE = new Set(["Administrator", "Production Engineer"]);

export default function ProductionRecordDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = Number(params.id);

  const [record, setRecord] = useState<ProductionEntry | null>(null);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    getProduction(id).then(setRecord).catch(() => setError("Unable to load this record."));
    getCurrentUser().then(setCurrentUser).catch(() => undefined);
  }, [id]);

  async function handleDelete() {
    if (!window.confirm("Delete this production record? This also removes its pressure/temperature data.")) {
      return;
    }
    setIsDeleting(true);
    try {
      await deleteProduction(id);
      router.push("/production/records");
    } catch {
      setError("Unable to delete this record.");
      setIsDeleting(false);
    }
  }

  if (error) return <p className="text-sm text-red-600 dark:text-red-400">{error}</p>;
  if (!record) return <p className="text-sm text-zinc-500 dark:text-zinc-400">Loading…</p>;

  const canManage = currentUser ? CAN_MANAGE.has(currentUser.role_name) : false;

  return (
    <div className="flex flex-1 flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <PageHeader
          title={`${record.well_code} — ${record.record_date}`}
          description={`${record.field_name} / ${record.facility_name}`}
        />
        {canManage ? (
          <div className="flex shrink-0 gap-2">
            <Link
              href={`/production/records/${record.id}/edit`}
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

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <InfoCard label="Oil" value={`${record.oil_bopd.toLocaleString()} BOPD`} />
        <InfoCard label="Gas" value={`${record.gas_mscfd.toLocaleString()} MSCFD`} />
        <InfoCard label="Water" value={`${record.water_bwpd.toLocaleString()} BWPD`} />
        <InfoCard label="Water Cut" value={record.water_cut_pct !== null ? `${record.water_cut_pct}%` : "—"} calculated />
        <InfoCard label="GOR" value={record.gor !== null ? `${record.gor} scf/bbl` : "—"} calculated />
        <InfoCard label="BOE" value={`${record.boe.toLocaleString()} boe/d`} calculated />
        <InfoCard label="Choke Size" value={record.choke_size !== null ? String(record.choke_size) : "—"} />
        <InfoCard label="Wellhead Pressure" value={record.wellhead_pressure !== null ? `${record.wellhead_pressure} psi` : "—"} />
        <InfoCard label="Tubing Pressure" value={record.tubing_pressure !== null ? `${record.tubing_pressure} psi` : "—"} />
        <InfoCard label="Casing Pressure" value={record.casing_pressure !== null ? `${record.casing_pressure} psi` : "—"} />
        <InfoCard label="Flowline Pressure" value={record.flowline_pressure !== null ? `${record.flowline_pressure} psi` : "—"} />
        <InfoCard
          label="Wellhead Temperature"
          value={record.wellhead_temperature !== null ? `${record.wellhead_temperature}°F` : "—"}
        />
        <InfoCard
          label="Downtime"
          value={record.downtime_hours > 0 ? `${record.downtime_hours} hrs` : "None"}
          calculated
        />
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
