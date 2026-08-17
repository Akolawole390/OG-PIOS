"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { AlertSeverityBadge } from "@/components/alerts/AlertSeverityBadge";
import { AlertStatusBadge } from "@/components/alerts/AlertStatusBadge";
import {
  acknowledgeAlert,
  addAlertNote,
  dismissAlert,
  getAlert,
  getAlertHistory,
  getCurrentUser,
  investigateAlert,
  resolveAlert,
  type AlertEntry,
  type AlertHistoryEntry,
  type CurrentUser,
} from "@/lib/api";

const CAN_ACT = new Set([
  "Administrator",
  "Production Operator",
  "Production Engineer",
  "Maintenance Engineer",
  "Management",
  "Analyst",
]);

function InfoItem({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">{label}</p>
      <p className="mt-1 text-sm text-zinc-900 dark:text-zinc-50">{value ?? "—"}</p>
    </div>
  );
}

export default function AlertDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);

  const [alert, setAlert] = useState<AlertEntry | null>(null);
  const [history, setHistory] = useState<AlertHistoryEntry[]>([]);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [note, setNote] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function load() {
    getAlert(id).then(setAlert).catch(() => setError("Unable to load this alert."));
    getAlertHistory(id).then((res) => setHistory(res.items)).catch(() => undefined);
  }

  useEffect(() => {
    load();
    getCurrentUser().then(setCurrentUser).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const canAct = currentUser ? CAN_ACT.has(currentUser.role_name) : false;

  async function runAction(action: (id: number, note?: string) => Promise<AlertEntry>) {
    setIsSubmitting(true);
    setError(null);
    try {
      await action(id, note.trim() || undefined);
      setNote("");
      load();
    } catch {
      setError("Unable to update this alert. Try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleSaveNote() {
    if (!note.trim()) return;
    setIsSubmitting(true);
    setError(null);
    try {
      await addAlertNote(id, note.trim());
      setNote("");
      load();
    } catch {
      setError("Unable to save this note. Try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (!alert) {
    return (
      <div className="flex flex-1 flex-col gap-6">
        <PageHeader title="Alert" description="Loading…" />
        {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <PageHeader title={alert.title} description={`${alert.category} · ${alert.alert_type}`} />
        <div className="flex shrink-0 items-center gap-2">
          <AlertSeverityBadge severity={alert.severity} />
          <AlertStatusBadge status={alert.status} />
        </div>
      </div>

      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

      <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Description</h3>
        <p className="mt-2 text-sm text-zinc-700 dark:text-zinc-300">{alert.description}</p>
        {alert.recommended_action ? (
          <>
            <h3 className="mt-4 text-sm font-semibold text-zinc-900 dark:text-zinc-50">Recommended Action</h3>
            <p className="mt-2 text-sm text-zinc-700 dark:text-zinc-300">{alert.recommended_action}</p>
          </>
        ) : null}
      </div>

      <div className="grid grid-cols-2 gap-4 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950 sm:grid-cols-4">
        <InfoItem label="Current Value" value={alert.current_value !== null ? `${alert.current_value} ${alert.unit ?? ""}` : null} />
        <InfoItem label="Threshold" value={alert.threshold_value !== null ? `${alert.threshold_value} ${alert.unit ?? ""}` : null} />
        <InfoItem label="Occurrences" value={String(alert.occurrence_count)} />
        <InfoItem label="Source" value={alert.source_module} />
        <InfoItem label="First Triggered" value={alert.triggered_at.slice(0, 19).replace("T", " ")} />
        <InfoItem label="Last Detected" value={alert.last_detected_at.slice(0, 19).replace("T", " ")} />
        <InfoItem label="Acknowledged" value={alert.acknowledged_at ? `${alert.acknowledged_at.slice(0, 19).replace("T", " ")} by ${alert.acknowledged_by_name ?? "—"}` : null} />
        <InfoItem label="Resolved" value={alert.resolved_at ? `${alert.resolved_at.slice(0, 19).replace("T", " ")} by ${alert.resolved_by_name ?? "—"}` : null} />
      </div>

      <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Affected Asset & Related Records</h3>
        <div className="mt-3 flex flex-wrap gap-4 text-sm">
          {alert.field_name ? <span>Field: {alert.field_name}</span> : null}
          {alert.facility_name ? <span>Facility: {alert.facility_name}</span> : null}
          {alert.well_id ? (
            <Link href={`/wells/${alert.well_id}`} className="text-zinc-900 hover:underline dark:text-zinc-50">
              Well: {alert.well_code}
            </Link>
          ) : null}
          {alert.equipment_id ? (
            <Link href={`/equipment/${alert.equipment_id}`} className="text-zinc-900 hover:underline dark:text-zinc-50">
              Equipment: {alert.equipment_tag}
            </Link>
          ) : null}
          {alert.maintenance_record_id ? (
            <Link href={`/maintenance/${alert.maintenance_record_id}`} className="text-zinc-900 hover:underline dark:text-zinc-50">
              Maintenance: {alert.maintenance_work_order_number ?? alert.maintenance_record_id}
            </Link>
          ) : null}
          {alert.production_loss_id ? (
            <Link href={`/production-loss/${alert.production_loss_id}`} className="text-zinc-900 hover:underline dark:text-zinc-50">
              Production Loss Event #{alert.production_loss_id}
            </Link>
          ) : null}
          {alert.category === "economics" ? (
            <Link href="/cost-revenue" className="text-zinc-900 hover:underline dark:text-zinc-50">
              Cost & Revenue Dashboard
            </Link>
          ) : null}
          {!alert.well_id && !alert.equipment_id && !alert.maintenance_record_id && !alert.production_loss_id && alert.category !== "economics" ? (
            <span className="text-zinc-500 dark:text-zinc-400">No linked records.</span>
          ) : null}
        </div>
      </div>

      {canAct ? (
        <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Actions</h3>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Optional note for the next action…"
            rows={2}
            className="mt-2 block w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          />
          <div className="mt-3 flex flex-wrap gap-2">
            <button type="button" disabled={isSubmitting} onClick={() => runAction(acknowledgeAlert)} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-900">
              Acknowledge
            </button>
            <button type="button" disabled={isSubmitting} onClick={() => runAction(investigateAlert)} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-900">
              Mark Investigating
            </button>
            <button type="button" disabled={isSubmitting} onClick={() => runAction(resolveAlert)} className="rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300">
              Resolve
            </button>
            <button type="button" disabled={isSubmitting} onClick={() => runAction(dismissAlert)} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-900">
              Dismiss
            </button>
            <button type="button" disabled={isSubmitting || !note.trim()} onClick={handleSaveNote} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-900">
              Save Note Only
            </button>
          </div>
        </div>
      ) : null}

      {alert.notes ? (
        <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Latest Note</h3>
          <p className="mt-2 text-sm text-zinc-700 dark:text-zinc-300">{alert.notes}</p>
        </div>
      ) : null}

      <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Status History</h3>
        {history.length > 0 ? (
          <ul className="mt-3 space-y-3 text-sm">
            {history.map((h) => (
              <li key={h.id} className="border-b border-zinc-100 pb-2 last:border-0 dark:border-zinc-900">
                <p className="font-medium text-zinc-900 dark:text-zinc-50">
                  {h.from_state ? `${h.from_state} → ${h.to_state}` : `Created (${h.to_state})`}
                </p>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">
                  {h.changed_at.slice(0, 19).replace("T", " ")} — {h.changed_by_name ?? "System"}
                </p>
                {h.note ? <p className="mt-1 text-sm text-zinc-700 dark:text-zinc-300">{h.note}</p> : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-sm text-zinc-500 dark:text-zinc-400">No history yet.</p>
        )}
      </div>

      <p className="text-xs text-zinc-400 dark:text-zinc-500">{alert.disclaimer_text}</p>
    </div>
  );
}
