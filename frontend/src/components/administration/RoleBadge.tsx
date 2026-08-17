"use client";

const ROLE_STYLES: Record<string, string> = {
  Administrator: "bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300",
  Management: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  "Production Engineer": "bg-teal-100 text-teal-800 dark:bg-teal-900/40 dark:text-teal-300",
  "Maintenance Engineer": "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  "Production Operator": "bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300",
  Analyst: "bg-cyan-100 text-cyan-800 dark:bg-cyan-900/40 dark:text-cyan-300",
  Viewer: "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
};

export function RoleBadge({ role }: { role: string }) {
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
        ROLE_STYLES[role] ?? ROLE_STYLES.Viewer
      }`}
    >
      {role}
    </span>
  );
}
