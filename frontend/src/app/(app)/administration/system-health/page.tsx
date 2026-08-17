"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { AdminGuard } from "@/components/administration/AdminGuard";
import { StatusCard } from "@/components/administration/StatusCard";
import { formatLabel } from "@/lib/format";
import { getAIConfig, getSystemHealth, type AIConfig, type SystemHealth } from "@/lib/api";

export default function SystemHealthPage() {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [aiConfig, setAiConfig] = useState<AIConfig | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getSystemHealth(), getAIConfig()])
      .then(([h, a]) => {
        setHealth(h);
        setAiConfig(a);
      })
      .catch(() => setError("Unable to load system health."));
  }, []);

  return (
    <AdminGuard>
      <div className="flex flex-1 flex-col gap-6">
        <PageHeader
          title="System Health"
          description="Backend, database, and AI configuration status. No infrastructure credentials or connection details are ever shown here."
        />

        {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

        {health ? (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <StatusCard label="Backend" value={formatLabel(health.backend_status)} />
            <StatusCard label="Database" value={formatLabel(health.database_status)} />
            <StatusCard label="API" value={formatLabel(health.api_status)} />
            <StatusCard label="App Version" value={health.app_version} />
            <StatusCard label="Environment" value={formatLabel(health.environment)} />
            <StatusCard label="AI Provider" value={formatLabel(health.ai_provider_status)} />
          </div>
        ) : !error ? (
          <p className="text-sm text-zinc-500 dark:text-zinc-400">Loading…</p>
        ) : null}

        {aiConfig ? (
          <div>
            <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-50">AI Configuration</h3>
            <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
              <dl className="flex flex-col gap-2 text-sm">
                <div className="flex justify-between">
                  <dt className="text-zinc-500 dark:text-zinc-400">Provider</dt>
                  <dd className="text-zinc-900 dark:text-zinc-50">{formatLabel(aiConfig.provider)}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-zinc-500 dark:text-zinc-400">Model</dt>
                  <dd className="text-zinc-900 dark:text-zinc-50">{aiConfig.model ?? "—"}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-zinc-500 dark:text-zinc-400">Status</dt>
                  <dd className="text-zinc-900 dark:text-zinc-50">{aiConfig.status}</dd>
                </div>
              </dl>
              <p className="mt-3 text-xs text-zinc-400 dark:text-zinc-500">
                API keys are configured server-side only and are never displayed here or anywhere else in the application. When
                no provider is configured, AI Insights and the What-If Simulator continue to work using deterministic,
                non-AI logic.
              </p>
            </div>
          </div>
        ) : null}
      </div>
    </AdminGuard>
  );
}
