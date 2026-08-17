"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { PageHeader } from "@/components/layout/PageHeader";
import { MaintenanceForm, type MaintenanceFormValues } from "@/components/maintenance/MaintenanceForm";
import {
  getMaintenance,
  updateMaintenance,
  type MaintenanceEntry,
  type MaintenancePayload,
  type MaintenancePriority,
  type MaintenanceStatus,
} from "@/lib/api";

function toFormValues(record: MaintenanceEntry): Partial<MaintenanceFormValues> {
  return {
    equipment_id: String(record.equipment_id),
    maintenance_type: record.maintenance_type,
    priority: record.priority as MaintenancePriority,
    status: record.status as MaintenanceStatus,
    description: record.description ?? "",
    planned_start_date: record.planned_start_date ?? "",
    planned_completion_date: record.planned_completion_date ?? "",
    start_date: record.start_date ?? "",
    completion_date: record.completion_date ?? "",
    technician_id: record.technician_id !== null ? String(record.technician_id) : "",
    labor_cost: record.labor_cost !== null ? String(record.labor_cost) : "",
    parts_cost: record.parts_cost !== null ? String(record.parts_cost) : "",
    contractor_cost: record.contractor_cost !== null ? String(record.contractor_cost) : "",
    other_cost: record.other_cost !== null ? String(record.other_cost) : "",
    downtime_hours: record.downtime_hours !== null ? String(record.downtime_hours) : "",
    failure_cause: record.failure_cause ?? "",
    corrective_action: record.corrective_action ?? "",
    notes: record.notes ?? "",
  };
}

export default function EditMaintenancePage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = Number(params.id);

  const [record, setRecord] = useState<MaintenanceEntry | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMaintenance(id).then(setRecord).catch(() => setError("Unable to load this work order."));
  }, [id]);

  async function handleSubmit(payload: MaintenancePayload) {
    const updated = await updateMaintenance(id, payload);
    router.push(`/maintenance/${updated.id}`);
  }

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title="Edit Work Order"
        description={record ? (record.work_order_number ?? `Work Order #${record.id}`) : "Loading…"}
      />
      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}
      {record ? (
        <MaintenanceForm
          initialValues={toFormValues(record)}
          submitLabel="Save Changes"
          lockEquipment
          onSubmit={handleSubmit}
        />
      ) : null}
    </div>
  );
}
