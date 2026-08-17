"use client";

import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/layout/PageHeader";
import { AdminGuard } from "@/components/administration/AdminGuard";
import { UserForm } from "@/components/administration/UserForm";
import { createUser, type UserCreatePayload } from "@/lib/api";

export default function NewUserPage() {
  const router = useRouter();

  async function handleSubmit(payload: UserCreatePayload) {
    const user = await createUser(payload);
    router.push(`/administration/users/${user.id}`);
  }

  return (
    <AdminGuard>
      <div className="flex flex-1 flex-col gap-6">
        <PageHeader title="New User" description="Create a new user account and assign a role." />
        <UserForm mode="create" submitLabel="Create User" onSubmit={handleSubmit} />
      </div>
    </AdminGuard>
  );
}
