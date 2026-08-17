"use client";

import type { PermissionMatrixEntry } from "@/lib/api";
import { RoleBadge } from "./RoleBadge";

export function PermissionMatrixTable({ entries }: { entries: PermissionMatrixEntry[] }) {
  const byModule = new Map<string, PermissionMatrixEntry[]>();
  for (const entry of entries) {
    const list = byModule.get(entry.module) ?? [];
    list.push(entry);
    byModule.set(entry.module, list);
  }

  return (
    <div className="flex flex-col gap-6">
      {Array.from(byModule.entries()).map(([module, moduleEntries]) => (
        <div key={module} className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-zinc-200 bg-zinc-50 text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
                <th className="px-4 py-2 font-medium" colSpan={2}>
                  {module}
                </th>
              </tr>
            </thead>
            <tbody>
              {moduleEntries.map((entry) => (
                <tr
                  key={`${entry.module}-${entry.action}`}
                  className="border-b border-zinc-100 last:border-0 dark:border-zinc-900"
                >
                  <td className="w-48 px-4 py-2.5 align-top font-medium text-zinc-900 dark:text-zinc-50">
                    {entry.action}
                  </td>
                  <td className="px-4 py-2.5">
                    {entry.roles.length === 0 ? (
                      <span className="text-xs italic text-zinc-400 dark:text-zinc-500">
                        {entry.note ?? "Not available"}
                      </span>
                    ) : (
                      <div className="flex flex-wrap items-center gap-1.5">
                        {entry.roles.map((role) => (
                          <RoleBadge key={role} role={role} />
                        ))}
                      </div>
                    )}
                    {entry.roles.length > 0 && entry.note ? (
                      <p className="mt-1 text-xs text-zinc-400 dark:text-zinc-500">{entry.note}</p>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}
