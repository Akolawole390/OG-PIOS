"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { getReportTypes, listReports, type ReportListItem, type ReportTypeInfo } from "@/lib/api";

const QUICK_ACTION_LABELS: Record<string, string> = {
  daily_operations: "Generate Daily Operations Report",
  weekly_production: "Generate Weekly Production Report",
  monthly_management: "Generate Monthly Management Report",
  what_if_scenario: "Generate What-If Scenario Report",
};

export default function ReportsPage() {
  const [types, setTypes] = useState<ReportTypeInfo[]>([]);
  const [recent, setRecent] = useState<ReportListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    getReportTypes().then((res) => setTypes(res.types)).catch(() => undefined);
    listReports({ sort: "last_generated_at", order: "desc", page_size: 8 })
      .then((res) => setRecent(res.items))
      .catch(() => undefined)
      .finally(() => setIsLoading(false));
  }, []);

  return (
    <div className="flex flex-1 flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <PageHeader
          title="Reports"
          description="Daily, weekly, and monthly production and operations reports, plus What-If scenario reports. Every figure traces back to existing OG-PIOS data — nothing here is invented."
        />
        <Link
          href="/reports/saved"
          className="shrink-0 rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900"
        >
          Saved Reports
        </Link>
      </div>

      <div>
        <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-50">Quick Report Generation</h3>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {types.map((t) => (
            <Link
              key={t.id}
              href={`/reports/builder?type=${t.id}`}
              className="rounded-lg border border-zinc-200 bg-white p-4 text-sm font-medium text-zinc-900 hover:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-50 dark:hover:border-zinc-600"
            >
              {QUICK_ACTION_LABELS[t.id] ?? `Generate ${t.label}`}
              <p className="mt-1 text-xs font-normal text-zinc-500 dark:text-zinc-400">{t.sections.length} available sections</p>
            </Link>
          ))}
        </div>
      </div>

      <div className="rounded-lg border border-dashed border-zinc-300 p-4 text-sm text-zinc-500 dark:border-zinc-700 dark:text-zinc-400">
        <span className="font-medium text-zinc-700 dark:text-zinc-300">Scheduled reports:</span> not yet implemented. Reports are
        generated on demand today; recurring schedules are a foundation for future work.
      </div>

      <div>
        <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-50">Recently Generated Reports</h3>
        {isLoading ? (
          <p className="text-sm text-zinc-500 dark:text-zinc-400">Loading…</p>
        ) : recent.length === 0 ? (
          <p className="text-sm text-zinc-500 dark:text-zinc-400">No reports generated yet.</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-zinc-200 bg-zinc-50 text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
                  <th className="px-4 py-2 font-medium">Name</th>
                  <th className="px-4 py-2 font-medium">Type</th>
                  <th className="px-4 py-2 font-medium">Generated</th>
                </tr>
              </thead>
              <tbody>
                {recent.map((item) => (
                  <tr key={item.id} className="border-b border-zinc-100 last:border-0 hover:bg-zinc-50 dark:border-zinc-900 dark:hover:bg-zinc-900">
                    <td className="px-4 py-2">
                      <Link href={`/reports/saved/${item.id}`} className="font-medium text-zinc-900 hover:underline dark:text-zinc-50">
                        {item.name}
                      </Link>
                    </td>
                    <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">{item.report_type}</td>
                    <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">
                      {item.last_generated_at ? item.last_generated_at.slice(0, 19).replace("T", " ") : "Never"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
