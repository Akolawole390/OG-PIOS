"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { AdminGuard } from "@/components/administration/AdminGuard";
import { RoleBadge } from "@/components/administration/RoleBadge";
import { listAdministrationUsers, listRoles, updateUser, type Role, type User } from "@/lib/api";

const PAGE_SIZE = 20;

export default function AdministrationUsersPage() {
  const [search, setSearch] = useState("");
  const [roleId, setRoleId] = useState("");
  const [activeFilter, setActiveFilter] = useState("");
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<User[]>([]);
  const [total, setTotal] = useState(0);
  const [roles, setRoles] = useState<Role[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [togglingId, setTogglingId] = useState<number | null>(null);

  function load() {
    setIsLoading(true);
    setError(null);
    listAdministrationUsers({
      search: search || undefined,
      role_id: roleId ? Number(roleId) : undefined,
      is_active: activeFilter === "" ? undefined : activeFilter === "true",
      page,
      page_size: PAGE_SIZE,
    })
      .then((res) => {
        setItems(res.items);
        setTotal(res.total);
      })
      .catch(() => setError("Unable to load users. Try again."))
      .finally(() => setIsLoading(false));
  }

  useEffect(() => {
    listRoles().then(setRoles).catch(() => undefined);
  }, []);

  useEffect(() => {
    const timeout = setTimeout(load, 250);
    return () => clearTimeout(timeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, roleId, activeFilter, page]);

  async function handleToggleActive(user: User) {
    setTogglingId(user.id);
    try {
      await updateUser(user.id, { is_active: !user.is_active });
      load();
    } catch {
      setError(`Unable to ${user.is_active ? "deactivate" : "activate"} this user. Try again.`);
    } finally {
      setTogglingId(null);
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <AdminGuard>
      <div className="flex flex-1 flex-col gap-6">
        <div className="flex items-start justify-between gap-4">
          <PageHeader title="User Management" description="Create, edit, activate, deactivate, and assign roles to users." />
          <Link
            href="/administration/users/new"
            className="shrink-0 rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
          >
            New User
          </Link>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <input
            type="search"
            placeholder="Search name or email…"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="w-64 rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          />
          <select
            value={roleId}
            onChange={(e) => { setRoleId(e.target.value); setPage(1); }}
            className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          >
            <option value="">All roles</option>
            {roles.map((r) => (
              <option key={r.id} value={r.id}>{r.name}</option>
            ))}
          </select>
          <select
            value={activeFilter}
            onChange={(e) => { setActiveFilter(e.target.value); setPage(1); }}
            className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          >
            <option value="">All statuses</option>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </select>
        </div>

        {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

        <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-zinc-200 bg-zinc-50 text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
                <th className="px-4 py-2 font-medium">Name</th>
                <th className="px-4 py-2 font-medium">Email</th>
                <th className="px-4 py-2 font-medium">Role</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr><td colSpan={5} className="px-4 py-6 text-center text-zinc-500 dark:text-zinc-400">Loading…</td></tr>
              ) : items.length === 0 ? (
                <tr><td colSpan={5} className="px-4 py-6 text-center text-zinc-500 dark:text-zinc-400">No users found.</td></tr>
              ) : (
                items.map((user) => (
                  <tr key={user.id} className="border-b border-zinc-100 last:border-0 hover:bg-zinc-50 dark:border-zinc-900 dark:hover:bg-zinc-900">
                    <td className="px-4 py-2">
                      <Link href={`/administration/users/${user.id}`} className="font-medium text-zinc-900 hover:underline dark:text-zinc-50">
                        {user.full_name}
                      </Link>
                    </td>
                    <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">{user.email}</td>
                    <td className="px-4 py-2"><RoleBadge role={user.role_name} /></td>
                    <td className="px-4 py-2">
                      <span
                        className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                          user.is_active
                            ? "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300"
                            : "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
                        }`}
                      >
                        {user.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right">
                      <button
                        type="button"
                        onClick={() => handleToggleActive(user)}
                        disabled={togglingId === user.id}
                        className="text-xs font-medium text-zinc-600 hover:underline disabled:opacity-40 dark:text-zinc-400"
                      >
                        {togglingId === user.id ? "Saving…" : user.is_active ? "Deactivate" : "Activate"}
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {total > 0 ? (
          <div className="flex items-center justify-between text-sm text-zinc-500 dark:text-zinc-400">
            <span>{total} user{total === 1 ? "" : "s"} — page {page} of {totalPages}</span>
            <div className="flex gap-2">
              <button type="button" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1} className="rounded-md border border-zinc-300 px-3 py-1 disabled:opacity-40 dark:border-zinc-700">
                Previous
              </button>
              <button type="button" onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages} className="rounded-md border border-zinc-300 px-3 py-1 disabled:opacity-40 dark:border-zinc-700">
                Next
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </AdminGuard>
  );
}
