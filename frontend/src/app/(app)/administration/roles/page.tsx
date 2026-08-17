"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { AdminGuard } from "@/components/administration/AdminGuard";
import { RoleBadge } from "@/components/administration/RoleBadge";
import { PermissionMatrixTable } from "@/components/administration/PermissionMatrixTable";
import { getPermissions, listRoles, type PermissionMatrixEntry, type Role } from "@/lib/api";

export default function RolesPage() {
  const [roles, setRoles] = useState<Role[]>([]);
  const [permissions, setPermissions] = useState<PermissionMatrixEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([listRoles(), getPermissions()])
      .then(([r, p]) => {
        setRoles(r);
        setPermissions(p);
      })
      .catch(() => setError("Unable to load roles and permissions."));
  }, []);

  return (
    <AdminGuard>
      <div className="flex flex-1 flex-col gap-6">
        <PageHeader
          title="Roles & Permissions"
          description="Roles are fixed by the application's authorization logic and cannot be created or deleted here — user role assignment happens on each user's profile."
        />

        {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

        <div>
          <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-50">Roles</h3>
          <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-zinc-200 bg-zinc-50 text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
                  <th className="px-4 py-2 font-medium">Role</th>
                  <th className="px-4 py-2 font-medium">Users</th>
                </tr>
              </thead>
              <tbody>
                {roles.map((role) => (
                  <tr key={role.id} className="border-b border-zinc-100 last:border-0 dark:border-zinc-900">
                    <td className="px-4 py-2"><RoleBadge role={role.name} /></td>
                    <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">{role.user_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div>
          <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-50">Permission Matrix</h3>
          <p className="mb-3 text-xs text-zinc-500 dark:text-zinc-400">
            This reflects the roles actually enforced by the API for each action — it is a read-only view, not an editable
            permission grant.
          </p>
          <PermissionMatrixTable entries={permissions} />
        </div>
      </div>
    </AdminGuard>
  );
}
