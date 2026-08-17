"use client";

import Link from "next/link";
import { type MaintenanceEntry } from "@/lib/api";
import { formatLabel } from "@/lib/format";

const STATUS_STYLES: Record<string, string> = {
  scheduled: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  open: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  in_progress: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  waiting_for_parts: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  completed: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  cancelled: "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
  overdue: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
};

const PRIORITY_STYLES: Record<string, string> = {
  critical: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
  high: "bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300",
  medium: "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
  low: "bg-zinc-100 text-zinc-600 dark:bg-zinc-900 dark:text-zinc-400",
};

export function MaintenanceStatusBadge({ status }: { status: string }) {
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[status] ?? STATUS_STYLES.scheduled}`}>
      {formatLabel(status)}
    </span>
  );
}

export function MaintenancePriorityBadge({ priority }: { priority: string }) {
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${PRIORITY_STYLES[priority] ?? PRIORITY_STYLES.medium}`}>
      {formatLabel(priority)}
    </span>
  );
}

type MaintenanceTableProps = {
  items: MaintenanceEntry[];
  isLoading: boolean;
  emptyMessage: string;
};

export function MaintenanceTable({ items, isLoading, emptyMessage }: MaintenanceTableProps) {
  return (
    <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-zinc-200 bg-zinc-50 text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
            <th className="px-4 py-2 font-medium">Work Order</th>
            <th className="px-4 py-2 font-medium">Equipment</th>
            <th className="px-4 py-2 font-medium">Type</th>
            <th className="px-4 py-2 font-medium">Priority</th>
            <th className="px-4 py-2 font-medium">Status</th>
            <th className="px-4 py-2 font-medium">Planned Completion</th>
            <th className="px-4 py-2 font-medium">Technician</th>
            <th className="px-4 py-2 font-medium">Cost</th>
          </tr>
        </thead>
        <tbody>
          {isLoading ? (
            <tr>
              <td colSpan={8} className="px-4 py-6 text-center text-zinc-500 dark:text-zinc-400">
                Loading…
              </td>
            </tr>
          ) : items.length === 0 ? (
            <tr>
              <td colSpan={8} className="px-4 py-6 text-center text-zinc-500 dark:text-zinc-400">
                {emptyMessage}
              </td>
            </tr>
          ) : (
            items.map((item) => (
              <tr key={item.id} className="border-b border-zinc-100 last:border-0 hover:bg-zinc-50 dark:border-zinc-900 dark:hover:bg-zinc-900">
                <td className="px-4 py-2">
                  <Link href={`/maintenance/${item.id}`} className="font-medium text-zinc-900 hover:underline dark:text-zinc-50">
                    {item.work_order_number ?? `#${item.id}`}
                  </Link>
                </td>
                <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">{item.equipment_tag}</td>
                <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">{formatLabel(item.maintenance_type)}</td>
                <td className="px-4 py-2">
                  <MaintenancePriorityBadge priority={item.priority} />
                </td>
                <td className="px-4 py-2">
                  <MaintenanceStatusBadge status={item.status} />
                </td>
                <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">{item.planned_completion_date ?? "—"}</td>
                <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">{item.technician_name ?? "Unassigned"}</td>
                <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">
                  {item.cost !== null ? `$${item.cost.toLocaleString()}` : "—"}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
