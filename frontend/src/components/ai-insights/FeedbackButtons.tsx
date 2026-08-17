"use client";

import { useState } from "react";
import { submitInsightFeedback, type FeedbackType, type InsightFeedbackEntry } from "@/lib/api";

const OPTIONS: { value: FeedbackType; label: string }[] = [
  { value: "useful", label: "Useful" },
  { value: "not_useful", label: "Not Useful" },
  { value: "incorrect", label: "Incorrect" },
  { value: "needs_review", label: "Needs Review" },
];

export function FeedbackButtons({
  insightId,
  existing,
  onSubmitted,
}: {
  insightId: number;
  existing: InsightFeedbackEntry[];
  onSubmitted: (feedback: InsightFeedbackEntry[]) => void;
}) {
  const [submitting, setSubmitting] = useState<FeedbackType | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleClick(feedback: FeedbackType) {
    setSubmitting(feedback);
    setError(null);
    try {
      const updated = await submitInsightFeedback(insightId, { feedback });
      onSubmitted(updated.feedback);
    } catch {
      setError("Unable to submit feedback. Try again.");
    } finally {
      setSubmitting(null);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-2">
        {OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            disabled={submitting !== null}
            onClick={() => handleClick(option.value)}
            className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
          >
            {submitting === option.value ? "Saving…" : option.label}
          </button>
        ))}
      </div>
      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}
      {existing.length > 0 ? (
        <ul className="space-y-1 text-xs text-zinc-500 dark:text-zinc-400">
          {existing.map((f) => (
            <li key={f.id}>
              {f.submitted_by_name ?? "Someone"} marked this <strong>{f.feedback.replace("_", " ")}</strong>
              {f.notes ? ` — "${f.notes}"` : ""}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
