"use client";

import { useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { askAssistant, type AssistantAnswer } from "@/lib/api";

type Message = {
  role: "user" | "assistant";
  text: string;
  sources?: AssistantAnswer["sources"];
  answeredBy?: AssistantAnswer["answered_by"];
};

const EXAMPLE_QUESTIONS = [
  "What are the biggest production problems today?",
  "Which wells lost the most production this month?",
  "Which equipment requires attention?",
  "Which wells have the highest maintenance cost?",
  "What are the biggest production-loss opportunities?",
  "Which field has the highest cost per barrel?",
  "What changed compared with last month?",
];

export default function AiOperationsAssistantPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || isSending) return;
    setError(null);
    setMessages((prev) => [...prev, { role: "user", text: trimmed }]);
    setQuestion("");
    setIsSending(true);
    try {
      const answer = await askAssistant(trimmed);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: answer.answer, sources: answer.sources, answeredBy: answer.answered_by },
      ]);
    } catch {
      setError("Unable to reach the assistant. It may be rate-limited — wait a minute and try again.");
    } finally {
      setIsSending(false);
    }
  }

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title="AI Operations Assistant"
        description="Ask questions answered from real OG-PIOS data only — never invented. Not a general-purpose chatbot."
      />

      <div className="flex flex-wrap gap-2">
        {EXAMPLE_QUESTIONS.map((q) => (
          <button
            key={q}
            type="button"
            onClick={() => send(q)}
            disabled={isSending}
            className="rounded-full border border-zinc-300 px-3 py-1 text-xs font-medium text-zinc-600 hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-900"
          >
            {q}
          </button>
        ))}
      </div>

      <div className="flex min-h-[300px] flex-1 flex-col gap-3 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
        {messages.length === 0 ? (
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            Ask a question above or type your own below — e.g. &quot;Why is well PBF-03-003 underperforming?&quot;
          </p>
        ) : (
          messages.map((message, index) => (
            <div
              key={index}
              className={`max-w-2xl rounded-lg px-4 py-2 text-sm ${
                message.role === "user"
                  ? "self-end bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                  : "self-start bg-zinc-100 text-zinc-900 dark:bg-zinc-900 dark:text-zinc-50"
              }`}
            >
              <p className="whitespace-pre-wrap">{message.text}</p>
              {message.role === "assistant" ? (
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  {message.answeredBy ? (
                    <span className="rounded border border-zinc-300 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-zinc-500 dark:border-zinc-700 dark:text-zinc-400">
                      {message.answeredBy === "deterministic" ? "From OG-PIOS data" : "AI-interpreted"}
                    </span>
                  ) : null}
                  {message.sources && message.sources.length > 0 ? (
                    <span className="text-[11px] text-zinc-500 dark:text-zinc-400">
                      Sources: {message.sources.map((s) => s.source_label).join(", ")}
                    </span>
                  ) : null}
                </div>
              ) : null}
            </div>
          ))
        )}
        {isSending ? <p className="self-start text-sm text-zinc-500 dark:text-zinc-400">Thinking…</p> : null}
      </div>

      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(question);
        }}
        className="flex gap-2"
      >
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question about production, equipment, maintenance, cost, or alerts…"
          className="flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
        />
        <button
          type="submit"
          disabled={isSending || !question.trim()}
          className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
        >
          Ask
        </button>
      </form>

      <p className="text-xs text-zinc-400 dark:text-zinc-500">
        Answers are sourced from OG-PIOS records with citations where available. Rule-based estimate requiring
        engineering review — not a guaranteed conclusion.
      </p>
    </div>
  );
}
