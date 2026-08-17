"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { getDailyBrief, type DailyBrief } from "@/lib/api";

export default function DailyOperationsBriefPage() {
  const [brief, setBrief] = useState<DailyBrief | null>(null);
  const [narrative, setNarrative] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    setIsLoading(true);
    getDailyBrief(narrative)
      .then(setBrief)
      .catch(() => undefined)
      .finally(() => setIsLoading(false));
  }, [narrative]);

  return (
    <div className="flex flex-1 flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <PageHeader
          title="OG-PIOS Daily Operations Intelligence"
          description={brief ? `Generated ${brief.generated_at.slice(0, 19).replace("T", " ")} — period: ${brief.period_label}` : "Loading…"}
        />
        <label className="flex shrink-0 items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400">
          <input type="checkbox" checked={narrative} onChange={(e) => setNarrative(e.target.checked)} />
          AI narrative
        </label>
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
