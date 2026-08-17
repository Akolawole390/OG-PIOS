"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { PageHeader } from "@/components/layout/PageHeader";
import { AdminGuard } from "@/components/administration/AdminGuard";
import { UserForm, type UserFormValues } from "@/components/administration/UserForm";
import { AuditLogTable } from "@/components/administration/AuditLogTable";
import { getUser, listAuditLog, updateUser, type AuditLogEntry, type User, type UserUpdatePayload } from "@/lib/api";

function toFormValues(user: User): Partial<UserFormValues> {
  return {
    email: user.email,
    full_name: user.full_name,
    role_id: String(user.role_id),
    is_active: user.is_active,
  };
}

export default function EditUserPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const userId = Number(params.id);

  const [user, setUser] = useState<User | null>(null);
  const [history, setHistory] = useState<AuditLogEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getUser(userId).then(setUser).catch(() => setError("Unable to load this user."));
    listAuditLog({ user_id: userId, page_size: 10 })
      .then((res) => setHistory(res.items))
      .catch(() => undefined);
  }, [userId]);

  async function handleSubmit(payload: UserUpdatePayload) {
    await updateUser(userId, payload);
    router.push("/administration/users");
  }

  return (
    <AdminGuard>
      <div className="flex flex-1 flex-col gap-6">
        <PageHeader title="Edit User" description={user ? `${user.full_name} (${user.email})` : "Loading…"} />
        {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}
        {user ? (
          <UserForm mode="edit" initialValues={toFormValues(user)} submitLabel="Save Changes" onSubmit={handleSubmit} />
        ) : null}

        <div>
          <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-50">Recent Activity for This User</h3>
          <AuditLogTable items={history} />
        </div>
      </div>
    </AdminGuard>
  );
}
