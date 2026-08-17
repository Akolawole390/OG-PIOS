"use client";

import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/layout/PageHeader";
import { EquipmentForm } from "@/components/equipment/EquipmentForm";
import { createEquipment, type EquipmentPayload } from "@/lib/api";

export default function NewEquipmentPage() {
  const router = useRouter();

  async function handleSubmit(payload: EquipmentPayload) {
    const equipment = await createEquipment(payload);
    router.push(`/equipment/${equipment.id}`);
  }

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader title="Add Equipment" description="Register a new equipment item and optionally associate it with a well or facility." />
      <EquipmentForm submitLabel="Create Equipment" onSubmit={handleSubmit} />
    </div>
  );
}
