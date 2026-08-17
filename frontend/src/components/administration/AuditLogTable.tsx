"use client";

import { formatLabel } from "@/lib/format";
import type { AuditLogEntry } from "@/lib/api";

export function AuditLogTable({
  items,
  onSelect,
}: {
  items: AuditLogEntry[];
  onSelect?: (entry: AuditLogEntry) => void;
}) {
  return (
    <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-zinc-200 bg-zinc-50 text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
            <th className="px-4 py-2 font-medium">Timestamp</th>
            <th className="px-4 py-2 font-medium">User</th>
            <th className="px-4 py-2 font-medium">Action</th>
            <th className="px-4 py-2 font-medium">Resource</th>
            <th className="px-4 py-2 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {items.length === 0 ? (
            <tr>
              <td colSpan={5} className="px-4 py-6 text-center text-zinc-500 dark:text-zinc-400">
                No audit events found.
              </td>
            </tr>
          ) : (
            items.map((entry) => (
              <tr
                key={entry.id}
                onClick={() => onSelect?.(entry)}
                className={`border-b border-zinc-100 last:border-0 dark:border-zinc-900 ${
                  onSelect ? "cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-900" : ""
                }`}
              >
                <td className="whitespace-nowrap px-4 py-2 text-zinc-700 dark:text-zinc-300">
                  {entry.created_at.slice(0, 19).replace("T", " ")}
                </td>
                <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">{entry.user_email ?? "System"}</td>
                <td className="px-4 py-2 font-medium text-zinc-900 dark:text-zinc-50">
                  {formatLabel(entry.action)}
                </td>
                <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">
                  {entry.entity_type ? formatLabel(entry.entity_type) : "—"}
                  {entry.entity_id ? ` #${entry.entity_id}` : ""}
                </td>
                <td className="px-4 py-2">
                  <span
                    className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                      entry.status === "success"
                        ? "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300"
                        : "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300"
                    }`}
                  >
                    {formatLabel(entry.status)}
                  </span>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
