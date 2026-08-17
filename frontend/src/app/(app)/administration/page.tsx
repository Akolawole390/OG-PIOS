"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { AdminGuard } from "@/components/administration/AdminGuard";
import { RoleBadge } from "@/components/administration/RoleBadge";
import { formatLabel } from "@/lib/format";
import { getAdminDashboard, type AdminDashboard } from "@/lib/api";

const QUICK_LINKS = [
  { href: "/administration/users", label: "User Management", hint: "Create, edit, activate, deactivate" },
  { href: "/administration/roles", label: "Roles & Permissions", hint: "Roles, user counts, permission matrix" },
  { href: "/administration/settings", label: "System Settings", hint: "Company, units, and operational thresholds" },
  { href: "/administration/audit-log", label: "Audit Log", hint: "Administrative and system activity trail" },
  { href: "/administration/system-health", label: "System Health", hint: "Backend, database, and AI configuration status" },
];

export default function AdministrationPage() {
  const [dashboard, setDashboard] = useState<AdminDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAdminDashboard()
      .then(setDashboard)
      .catch(() => setError("Unable to load the administration dashboard."));
  }, []);

  return (
    <AdminGuard>
      <div className="flex flex-1 flex-col gap-6">
        <PageHeader
          title="Administration"
          description="Users, roles, permissions, system settings, operational thresholds, AI configuration status, and the audit trail."
        />

        {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

        {dashboard ? (
          <>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <KpiCard label="Total Users" value={String(dashboard.total_users)} />
              <KpiCard label="Active Users" value={String(dashboard.active_users)} />
              <KpiCard label="Inactive Users" value={String(dashboard.inactive_users)} />
              <KpiCard
                label="AI Provider"
                value={dashboard.ai_provider_configured ? "Configured" : "Not configured"}
                hint={dashboard.ai_provider_configured ? undefined : "Deterministic fallback active"}
              />
            </div>

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <div>
                <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-50">Users by Role</h3>
                <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
                  <ul className="flex flex-col gap-2">
                    {dashboard.roles.map((r) => (
                      <li key={r.role_name} className="flex items-center justify-between text-sm">
                        <RoleBadge role={r.role_name} />
                        <span className="font-medium text-zinc-900 dark:text-zinc-50">{r.user_count}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              <div>
                <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-50">Recent Administrative Activity</h3>
                <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
                  {dashboard.recent_activity.length === 0 ? (
                    <p className="text-sm text-zinc-500 dark:text-zinc-400">No activity recorded yet.</p>
                  ) : (
                    <ul className="flex flex-col gap-2 text-sm">
                      {dashboard.recent_activity.map((event) => (
                        <li key={event.id} className="flex items-center justify-between gap-3">
                          <span className="text-zinc-700 dark:text-zinc-300">
                            {formatLabel(event.action)}
                            {event.user_email ? ` — ${event.user_email}` : ""}
                          </span>
                          <span className="shrink-0 text-xs text-zinc-400 dark:text-zinc-500">
                            {event.created_at.slice(0, 19).replace("T", " ")}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                  <Link
                    href="/administration/audit-log"
                    className="mt-3 inline-block text-xs font-medium text-zinc-600 hover:underline dark:text-zinc-400"
                  >
                    View full audit log →
                  </Link>
                </div>
              </div>
            </div>
          </>
        ) : !error ? (
          <p className="text-sm text-zinc-500 dark:text-zinc-400">Loading…</p>
        ) : null}

        <div>
          <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-50">Manage</h3>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {QUICK_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="rounded-lg border border-zinc-200 bg-white p-4 text-sm font-medium text-zinc-900 hover:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-50 dark:hover:border-zinc-600"
              >
                {link.label}
                <p className="mt-1 text-xs font-normal text-zinc-500 dark:text-zinc-400">{link.hint}</p>
              </Link>
            ))}
          </div>
        </div>
      </div>
    </AdminGuard>
  );
}
