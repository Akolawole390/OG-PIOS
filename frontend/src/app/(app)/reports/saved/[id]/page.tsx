"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { ReportViewer } from "@/components/reports/ReportViewer";
import {
  deleteReport,
  exportReport,
  getCurrentUser,
  getReport,
  regenerateReport,
  updateReport,
  type CurrentUser,
  type Report,
} from "@/lib/api";
import { formatLabel } from "@/lib/format";

const CAN_ACT = new Set([
  "Administrator",
  "Production Operator",
  "Production Engineer",
  "Maintenance Engineer",
  "Management",
  "Analyst",
]);

export default function ReportDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = Number(params.id);

  const [report, setReport] = useState<Report | null>(null);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);

  const [isRenaming, setIsRenaming] = useState(false);
  const [nameDraft, setNameDraft] = useState("");
  const [descriptionDraft, setDescriptionDraft] = useState("");

  function load() {
    getReport(id)
      .then((r) => {
        setReport(r);
        setNameDraft(r.name);
        setDescriptionDraft(r.description ?? "");
      })
      .catch(() => setError("Unable to load this report."));
  }

  useEffect(() => {
    load();
    getCurrentUser().then(setCurrentUser).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const canAct = currentUser ? CAN_ACT.has(currentUser.role_name) : false;

  async function handleRename() {
    if (!nameDraft.trim()) return;
    setIsBusy(true);
    setError(null);
    try {
      await updateReport(id, { name: nameDraft.trim(), description: descriptionDraft.trim() || null });
      setIsRenaming(false);
      load();
    } catch {
      setError("Unable to rename this report.");
    } finally {
      setIsBusy(false);
    }
  }

  async function handleRegenerate() {
    setIsBusy(true);
    setError(null);
    try {
      await regenerateReport(id);
      load();
    } catch {
      setError("Unable to regenerate this report against current data.");
    } finally {
      setIsBusy(false);
    }
  }

  async function handleDelete() {
    if (!window.confirm("Delete this report? This cannot be undone.")) return;
    setIsBusy(true);
    try {
      await deleteReport(id);
      router.push("/reports/saved");
    } catch {
      setError("Unable to delete this report.");
      setIsBusy(false);
    }
  }

  async function handleExport(format: "csv" | "pdf") {
    setIsBusy(true);
    setError(null);
    try {
      await exportReport(id, format, `${report?.name ?? "report"}.${format}`);
    } catch {
      setError(`Unable to export as ${format.toUpperCase()}.`);
    } finally {
      setIsBusy(false);
    }
  }

  if (!report) {
    return (
      <div className="flex flex-1 flex-col gap-6">
        <PageHeader title="Report" description="Loading…" />
        {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        {isRenaming ? (
          <div className="flex flex-1 flex-col gap-2">
            <input
              value={nameDraft}
              onChange={(e) => setNameDraft(e.target.value)}
              className="rounded-md border border-zinc-300 px-3 py-2 text-lg font-semibold dark:border-zinc-700 dark:bg-zinc-900"
            />
            <input
              value={descriptionDraft}
              onChange={(e) => setDescriptionDraft(e.target.value)}
              placeholder="Description (optional)"
              className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
            />
            <div className="flex gap-2">
              <button type="button" onClick={handleRename} disabled={isBusy} className="rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900">
                Save Name
              </button>
              <button type="button" onClick={() => setIsRenaming(false)} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900">
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <PageHeader
            title={report.name}
            description={report.description ?? `${formatLabel(report.report_type)} · ${report.period_start?.slice(0, 10) ?? "—"} to ${report.period_end?.slice(0, 10) ?? "—"}`}
          />
        )}
      </div>

      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

      <div className="flex flex-wrap gap-2">
        {canAct && !isRenaming ? (
          <button type="button" onClick={() => setIsRenaming(true)} disabled={isBusy} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-900">
            Rename
          </button>
        ) : null}
        {canAct ? (
          <button type="button" onClick={handleRegenerate} disabled={isBusy} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-900">
            {isBusy ? "Working…" : "Regenerate Against Current Data"}
          </button>
        ) : null}
        <button type="button" onClick={() => handleExport("csv")} disabled={isBusy} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-900">
          Export CSV
        </button>
        <button type="button" onClick={() => handleExport("pdf")} disabled={isBusy} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-900">
          Export PDF
        </button>
        {canAct ? (
          <button type="button" onClick={handleDelete} disabled={isBusy} className="rounded-md border border-red-300 px-3 py-1.5 text-sm font-medium text-red-600 hover:bg-red-50 disabled:opacity-50 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-950/40">
            Delete
          </button>
        ) : null}
      </div>

      <p className="text-xs text-zinc-400 dark:text-zinc-500">
        Calculation version {report.calculation_version} · Last generated{" "}
        {report.last_generated_at ? report.last_generated_at.slice(0, 19).replace("T", " ") : "never"}
      </p>

      {!report.results ? (
        <p className="text-sm text-zinc-500 dark:text-zinc-400">This report has not been generated yet.</p>
      ) : (
        <ReportViewer results={report.results} />
      )}

      <p className="text-xs text-zinc-400 dark:text-zinc-500">
        <Link href="/reports/saved" className="underline-offset-2 hover:underline">
          Back to saved reports
        </Link>
      </p>
    </div>
  );
}
