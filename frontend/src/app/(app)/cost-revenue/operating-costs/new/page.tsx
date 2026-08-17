"use client";

import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/layout/PageHeader";
import { OperatingCostForm } from "@/components/cost-revenue/OperatingCostForm";
import { createOperatingCost, type OperatingCostPayload } from "@/lib/api";

export default function NewOperatingCostPage() {
  const router = useRouter();

  async function handleSubmit(payload: OperatingCostPayload) {
    const record = await createOperatingCost(payload);
    router.push(`/cost-revenue/operating-costs/${record.id}`);
  }

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader title="Add Operating Cost" description="Record a field, facility, well, or equipment-level operating cost." />
      <OperatingCostForm submitLabel="Create Record" onSubmit={handleSubmit} />
    </div>
  );
}
