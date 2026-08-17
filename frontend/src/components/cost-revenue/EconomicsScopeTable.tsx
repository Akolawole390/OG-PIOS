"use client";

import Link from "next/link";
import { type EconomicsScopeRow } from "@/lib/api";
import { MultiCurrencyAmount } from "@/components/cost-revenue/MultiCurrencyAmount";

type EconomicsScopeTableProps = {
  rows: EconomicsScopeRow[];
  isLoading: boolean;
};

function detailHref(row: EconomicsScopeRow): string | null {
  if (row.scope === "well") return `/wells/${row.key}`;
  return null;
}

function FlagBadge({ label, active }: { label: string; active: boolean }) {
  if (!active) return null;
  return (
    <span className="inline-block rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
      {label}
    </span>
  );
}

export function EconomicsScopeTable({ rows, isLoading }: EconomicsScopeTableProps) {
  return (
    <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-zinc-200 bg-zinc-50 text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
            <th className="px-4 py-2 font-medium">Name</th>
            <th className="px-4 py-2 font-medium">Oil (bbl)</th>
            <th className="px-4 py-2 font-medium">BOE</th>
            <th className="px-4 py-2 font-medium">Revenue</th>
            <th className="px-4 py-2 font-medium">Operating Cost</th>
            <th className="px-4 py-2 font-medium">Maintenance Cost</th>
            <th className="px-4 py-2 font-medium">Lost Revenue</th>
            <th className="px-4 py-2 font-medium">Margin</th>
            <th className="px-4 py-2 font-medium">Cost/bbl</th>
            <th className="px-4 py-2 font-medium">Flags</th>
          </tr>
        </thead>
        <tbody>
          {isLoading ? (
            <tr>
              <td colSpan={10} className="px-4 py-6 text-center text-zinc-500 dark:text-zinc-400">
                Loading…
              </td>
            </tr>
          ) : rows.length === 0 ? (
            <tr>
              <td colSpan={10} className="px-4 py-6 text-center text-zinc-500 dark:text-zinc-400">
                No data available yet.
              </td>
            </tr>
          ) : (
            rows.map((row) => {
              const href = detailHref(row);
              return (
                <tr key={row.key} className="border-b border-zinc-100 last:border-0 hover:bg-zinc-50 dark:border-zinc-900 dark:hover:bg-zinc-900">
                  <td className="px-4 py-2 font-medium text-zinc-900 dark:text-zinc-50">
                    {href ? <Link href={href} className="hover:underline">{row.label}</Link> : row.label}
                  </td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">{row.oil_bbl.toLocaleString()}</td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">{row.boe.toLocaleString()}</td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300"><MultiCurrencyAmount amounts={row.revenue} /></td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300"><MultiCurrencyAmount amounts={row.operating_cost} /></td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">${row.maintenance_cost.toLocaleString()}</td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300"><MultiCurrencyAmount amounts={row.production_loss_revenue} /></td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">
                    {row.margin.length > 0 ? <MultiCurrencyAmount amounts={row.margin} /> : (
                      <span className="text-xs text-zinc-400 dark:text-zinc-500">N/A</span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300"><MultiCurrencyAmount amounts={row.cost_per_bbl} /></td>
                  <td className="px-4 py-2">
                    {row.review_note ? (
                      <span className="text-xs italic text-zinc-500 dark:text-zinc-400">{row.review_note}</span>
                    ) : (
                      <div className="flex flex-wrap gap-1">
                        <FlagBadge label="High production" active={!!row.high_production} />
                        <FlagBadge label="High cost" active={!!row.high_cost} />
                        <FlagBadge label="Low margin" active={!!row.low_margin} />
                        <FlagBadge label="High loss" active={!!row.high_loss} />
                      </div>
                    )}
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
