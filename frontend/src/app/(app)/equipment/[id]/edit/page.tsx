"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { PageHeader } from "@/components/layout/PageHeader";
import { EquipmentForm, type EquipmentFormValues } from "@/components/equipment/EquipmentForm";
import { getEquipment, updateEquipment, type Equipment, type EquipmentPayload, type EquipmentStatus } from "@/lib/api";

function toFormValues(equipment: Equipment): Partial<EquipmentFormValues> {
  return {
    equipment_tag: equipment.equipment_tag,
    name: equipment.name,
    equipment_type: equipment.equipment_type,
    manufacturer: equipment.manufacturer ?? "",
    model: equipment.model ?? "",
    serial_number: equipment.serial_number ?? "",
    installation_date: equipment.installation_date ?? "",
    commissioning_date: equipment.commissioning_date ?? "",
    description: equipment.description ?? "",
    status: equipment.status as EquipmentStatus,
    operating_hours: equipment.operating_hours !== null ? String(equipment.operating_hours) : "",
    next_maintenance_due: equipment.next_maintenance_due ?? "",
    facility_id: equipment.facility_id !== null ? String(equipment.facility_id) : "",
    well_id: equipment.well_id !== null ? String(equipment.well_id) : "",
  };
}

export default function EditEquipmentPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = Number(params.id);

  const [equipment, setEquipment] = useState<Equipment | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getEquipment(id).then(setEquipment).catch(() => setError("Unable to load this equipment record."));
  }, [id]);

  async function handleSubmit(payload: EquipmentPayload) {
    const updated = await updateEquipment(id, payload);
    router.push(`/equipment/${updated.id}`);
  }

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader title="Edit Equipment" description={equipment ? equipment.name : "Loading…"} />
      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}
      {equipment ? (
        <EquipmentForm initialValues={toFormValues(equipment)} submitLabel="Save Changes" onSubmit={handleSubmit} />
      ) : null}
    </div>
  );
}
