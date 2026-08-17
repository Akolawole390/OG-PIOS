"use client";

import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/layout/PageHeader";
import { ProductionForm } from "@/components/production/ProductionForm";
import { createProduction, type ProductionPayload } from "@/lib/api";

export default function NewProductionRecordPage() {
  const router = useRouter();

  async function handleSubmit(payload: ProductionPayload) {
    const record = await createProduction(payload);
    return { id: record.id, warnings: record.warnings };
  }

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader title="Add Production Record" description="Enter a daily production entry for a well." />
      <ProductionForm
        submitLabel="Create Record"
        onSubmit={handleSubmit}
        onSaved={(id) => router.push(`/production/records/${id}`)}
      />
    </div>
  );
}
