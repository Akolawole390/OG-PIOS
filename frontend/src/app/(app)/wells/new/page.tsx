"use client";

import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/layout/PageHeader";
import { WellForm } from "@/components/wells/WellForm";
import { createWell, type WellPayload } from "@/lib/api";

export default function NewWellPage() {
  const router = useRouter();

  async function handleSubmit(payload: WellPayload) {
    const well = await createWell(payload);
    router.push(`/wells/${well.id}`);
  }

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader title="Add Well" description="Register a new well against an existing facility." />
      <WellForm submitLabel="Create Well" onSubmit={handleSubmit} />
    </div>
  );
}
