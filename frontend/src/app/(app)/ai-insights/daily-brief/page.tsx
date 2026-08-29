"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { exportDailyBriefPdf, getDailyBrief, type DailyBrief } from "@/lib/api";

function briefToPlainText(brief: DailyBrief): string {
  const lines = [
    "OG-PIOS Daily Operations Intelligence",
    `Generated ${brief.generated_at.slice(0, 19).replace("T", " ")} — period: ${brief.period_label}`,
    "",
  ];
  if (brief.narrative) {
    lines.push("Narrative Summary", brief.narrative, "");
  }
  for (const section of brief.sections) {
    lines.push(section.title, section.summary);
    for (const item of section.items) lines.push(`- ${item}`);
    lines.push("");
  }
  lines.push(brief.disclaimer_text);
  return lines.join("\n");
}

export default function DailyOperationsBriefPage() {
  const [brief, setBrief] = useState<DailyBrief | null>(null);
  const [narrative, setNarrative] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isExporting, setIsExporting] = useState(false);
  const [copyMessage, setCopyMessage] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  useEffect(() => {
    setIsLoading(true);
    getDailyBrief(narrative)
      .then(setBrief)
      .catch(() => undefined)
      .finally(() => setIsLoading(false));
  }, [narrative]);

  async function handleCopy() {
    if (!brief) return;
    try {
      await navigator.clipboard.writeText(briefToPlainText(brief));
      setCopyMessage("Copied to clipboard.");
    } catch {
      setCopyMessage("Unable to copy — try selecting and copying manually.");
    } finally {
      setTimeout(() => setCopyMessage(null), 3000);
    }
  }

  async function handleExport() {
    setIsExporting(true);
    setExportError(null);
    try {
      await exportDailyBriefPdf(narrative);
    } catch {
      setExportError("Unable to export as PDF. Try again.");
    } finally {
      setIsExporting(false);
    }
  }

  return (
    <div className="flex flex-1 flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <PageHeader
          title="OG-PIOS Daily Operations Intelligence"
          description={brief ? `Generated ${brief.generated_at.slice(0, 19).replace("T", " ")} — period: ${brief.period_label}` : "Loading…"}
        />
        <div className="flex shrink-0 flex-col items-end gap-2">
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400">
              <input type="checkbox" checked={narrative} onChange={(e) => setNarrative(e.target.checked)} />
              AI narrative
            </label>
            <button
              type="button"
              onClick={handleCopy}
              disabled={!brief}
              className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium text-zinc-700 hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
            >
              Copy
            </button>
            <button
              type="button"
              onClick={handleExport}
              disabled={!brief || isExporting}
              className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium text-zinc-700 hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
            >
              {isExporting ? "Exporting…" : "Export PDF"}
            </button>
          </div>
          {copyMessage ? <p className="text-xs text-zinc-500 dark:text-zinc-400">{copyMessage}</p> : null}
          {exportError ? <p className="text-xs text-red-600 dark:text-red-400">{exportError}</p> : null}
        </div>
      </div>

      {isLoading ? (
        <p className="text-sm text-zinc-500 dark:text-zinc-400">Loading…</p>
      ) : brief ? (
        <>
          {brief.narrative ? (
            <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
              <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Narrative Summary</h3>
              <p className="mt-2 whitespace-pre-wrap text-sm text-zinc-700 dark:text-zinc-300">{brief.narrative}</p>
            </div>
          ) : null}

          <div className="flex flex-col gap-4">
            {brief.sections.map((section) => (
              <div key={section.title} className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
                <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">{section.title}</h3>
                <p className="mt-1 text-sm text-zinc-700 dark:text-zinc-300">{section.summary}</p>
                {section.items.length > 0 ? (
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-zinc-600 dark:text-zinc-400">
                    {section.items.map((item, i) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ))}
          </div>

          <p className="text-xs text-zinc-400 dark:text-zinc-500">{brief.disclaimer_text}</p>
        </>
      ) : (
        <p className="text-sm text-red-600 dark:text-red-400">Unable to load the daily brief.</p>
      )}
    </div>
  );
}
