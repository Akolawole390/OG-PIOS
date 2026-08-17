"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { PageHeader } from "@/components/layout/PageHeader";
import { ProductionLossForm } from "@/components/production-loss/ProductionLossForm";
import { createProductionLoss, type ProductionLossPayload } from "@/lib/api";

export default function NewProductionLossPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const equipmentId = searchParams.get("equipment_id");

  async function handleSubmit(payload: ProductionLossPayload) {
    const record = await createProductionLoss(payload);
    router.push(`/production-loss/${record.id}`);
  }

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title="Add Production Loss Record"
        description="Estimated production loss and financial impact are calculated automatically where data is available."
      />
      <ProductionLossForm
        submitLabel="Create Record"
        initialValues={equipmentId ? { equipment_id: equipmentId } : undefined}
        onSubmit={handleSubmit}
      />
    </div>
  );
}
