"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { PageHeader } from "@/components/layout/PageHeader";
import { MaintenanceForm } from "@/components/maintenance/MaintenanceForm";
import { createMaintenance, type MaintenancePayload } from "@/lib/api";

export default function NewMaintenancePage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const equipmentId = searchParams.get("equipment_id");

  async function handleSubmit(payload: MaintenancePayload) {
    const record = await createMaintenance(payload);
    router.push(`/maintenance/${record.id}`);
  }

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader title="Create Work Order" description="Schedule or log a maintenance activity for a piece of equipment." />
      <MaintenanceForm
        submitLabel="Create Work Order"
        initialValues={equipmentId ? { equipment_id: equipmentId } : undefined}
        onSubmit={handleSubmit}
      />
    </div>
  );
}
