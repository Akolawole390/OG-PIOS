"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { EconomicsScopeTable } from "@/components/cost-revenue/EconomicsScopeTable";
import { getEconomicsByScope, type EconomicsScopeRow } from "@/lib/api";

const RANK_OPTIONS = [
  { value: "production", label: "Production" },
  { value: "revenue", label: "Revenue" },
  { value: "cost_efficiency", label: "Cost Efficiency" },
  { value: "margin", label: "Estimated Margin" },
] as const;

export default function FieldEconomicsPage() {
  const [rankBy, setRankBy] = useState<(typeof RANK_OPTIONS)[number]["value"]>("production");
  const [rows, setRows] = useState<EconomicsScopeRow[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    setIsLoading(true);
    getEconomicsByScope({ scope: "field", rank_by: rankBy })
      .then((res) => setRows(res.rows))
      .catch(() => undefined)
      .finally(() => setIsLoading(false));
  }, [rankBy]);

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader title="Field Economics" description="Production, revenue, cost, and estimated margin compared across fields." />

      <div className="flex items-center gap-3">
        <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Rank by</label>
        <select value={rankBy} onChange={(e) => setRankBy(e.target.value as typeof rankBy)} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          {RANK_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>

      <EconomicsScopeTable rows={rows} isLoading={isLoading} />

      <p className="text-xs text-zinc-400 dark:text-zinc-500">
        All figures are estimates for the latest available production month — see each field&apos;s detail for the
        underlying records.
      </p>
    </div>
  );
}
