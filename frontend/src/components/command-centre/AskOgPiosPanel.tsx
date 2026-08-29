"use client";

import Link from "next/link";
import { useState } from "react";
import { askAssistant, type AssistantAnswer } from "@/lib/api";

export function AskOgPiosPanel() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<AssistantAnswer | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || isSending) return;
    setError(null);
    setIsSending(true);
    try {
      const result = await askAssistant(trimmed);
      setAnswer(result);
    } catch {
      setError("Unable to reach the assistant. It may be rate-limited — wait a minute and try again.");
    } finally {
      setIsSending(false);
    }
  }

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Ask OG-PIOS</h3>
        <Link href="/ai-insights/assistant" className="text-xs font-medium text-zinc-600 hover:underline dark:text-zinc-400">
          Open full assistant →
        </Link>
      </div>

      <form onSubmit={handleSubmit} className="mt-3 flex gap-2">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g. Which wells lost the most production this month?"
          className="flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
        />
        <button
          type="submit"
          disabled={isSending || !question.trim()}
          className="shrink-0 rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
        >
          {isSending ? "Asking…" : "Ask"}
        </button>
      </form>

      {error ? <p className="mt-3 text-sm text-red-600 dark:text-red-400">{error}</p> : null}

      {answer ? (
        <div className="mt-3 rounded-lg bg-zinc-100 p-3 text-sm text-zinc-900 dark:bg-zinc-900 dark:text-zinc-50">
          <p className="whitespace-pre-wrap">{answer.answer}</p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span className="rounded border border-zinc-300 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-zinc-500 dark:border-zinc-700 dark:text-zinc-400">
              {answer.answered_by === "deterministic" ? "From OG-PIOS data" : "AI-interpreted"}
            </span>
            {answer.sources.length > 0 ? (
              <span className="text-[11px] text-zinc-500 dark:text-zinc-400">
                Sources: {answer.sources.map((s) => s.source_label).join(", ")}
              </span>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
