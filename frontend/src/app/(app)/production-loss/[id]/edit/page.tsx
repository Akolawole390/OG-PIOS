"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { PageHeader } from "@/components/layout/PageHeader";
import { ProductionLossForm, type ProductionLossFormValues } from "@/components/production-loss/ProductionLossForm";
import {
  getProductionLoss,
  updateProductionLoss,
  type ProductionLossCategory,
  type ProductionLossEntry,
  type ProductionLossPayload,
} from "@/lib/api";

function toFormValues(record: ProductionLossEntry): Partial<ProductionLossFormValues> {
  return {
    loss_date: record.loss_date,
    category: (record.category as ProductionLossCategory) ?? "",
    cause: record.cause ?? "",
    downtime_hours: record.downtime_hours !== null ? String(record.downtime_hours) : "",
    well_id: record.well_id !== null ? String(record.well_id) : "",
    equipment_id: record.equipment_id !== null ? String(record.equipment_id) : "",
    downtime_event_id: record.downtime_event_id !== null ? String(record.downtime_event_id) : "",
    maintenance_record_id: record.maintenance_record_id !== null ? String(record.maintenance_record_id) : "",
    estimated_bopd_lost: record.estimated_bopd_lost !== null ? String(record.estimated_bopd_lost) : "",
    estimated_mscf_lost: record.estimated_mscf_lost !== null ? String(record.estimated_mscf_lost) : "",
    estimated_revenue_impact: record.estimated_revenue_impact !== null ? String(record.estimated_revenue_impact) : "",
    currency: record.currency ?? "",
  };
}

export default function EditProductionLossPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = Number(params.id);

  const [record, setRecord] = useState<ProductionLossEntry | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getProductionLoss(id).then(setRecord).catch(() => setError("Unable to load this record."));
  }, [id]);

  async function handleSubmit(payload: ProductionLossPayload) {
    const updated = await updateProductionLoss(id, payload);
    router.push(`/production-loss/${updated.id}`);
  }

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader title="Edit Production Loss Record" description={record ? `Loss on ${record.loss_date}` : "Loading…"} />
      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}
      {record ? (
        <ProductionLossForm initialValues={toFormValues(record)} submitLabel="Save Changes" onSubmit={handleSubmit} />
      ) : null}
    </div>
  );
}
