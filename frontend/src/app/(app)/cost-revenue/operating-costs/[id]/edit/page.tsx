"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { PageHeader } from "@/components/layout/PageHeader";
import { OperatingCostForm, type OperatingCostFormValues } from "@/components/cost-revenue/OperatingCostForm";
import {
  getOperatingCost,
  updateOperatingCost,
  type CostCurrency,
  type OperatingCostEntry,
  type OperatingCostPayload,
} from "@/lib/api";

function toFormValues(record: OperatingCostEntry): Partial<OperatingCostFormValues> {
  return {
    cost_date: record.cost_date,
    category: record.category,
    amount: String(record.amount),
    currency: record.currency as CostCurrency,
    description: record.description ?? "",
    cost_period: record.cost_period ?? "",
    source: record.source ?? "",
    notes: record.notes ?? "",
    field_id: record.field_id !== null ? String(record.field_id) : "",
    facility_id: record.facility_id !== null ? String(record.facility_id) : "",
    well_id: record.well_id !== null ? String(record.well_id) : "",
    equipment_id: record.equipment_id !== null ? String(record.equipment_id) : "",
  };
}

export default function EditOperatingCostPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = Number(params.id);

  const [record, setRecord] = useState<OperatingCostEntry | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getOperatingCost(id).then(setRecord).catch(() => setError("Unable to load this record."));
  }, [id]);

  async function handleSubmit(payload: OperatingCostPayload) {
    const updated = await updateOperatingCost(id, payload);
    router.push(`/cost-revenue/operating-costs/${updated.id}`);
  }

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader title="Edit Operating Cost" description={record ? `${record.category} — ${record.cost_date}` : "Loading…"} />
      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}
      {record ? (
        <OperatingCostForm initialValues={toFormValues(record)} submitLabel="Save Changes" onSubmit={handleSubmit} />
      ) : null}
    </div>
  );
}
