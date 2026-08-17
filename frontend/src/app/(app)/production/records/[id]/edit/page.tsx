"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { PageHeader } from "@/components/layout/PageHeader";
import { ProductionForm, type ProductionFormValues } from "@/components/production/ProductionForm";
import { getProduction, updateProduction, type ProductionEntry, type ProductionPayload } from "@/lib/api";

function toFormValues(record: ProductionEntry): Partial<ProductionFormValues> {
  return {
    well_id: String(record.well_id),
    record_date: record.record_date,
    oil_bopd: String(record.oil_bopd),
    gas_mscfd: String(record.gas_mscfd),
    water_bwpd: String(record.water_bwpd),
    choke_size: record.choke_size !== null ? String(record.choke_size) : "",
    wellhead_pressure: record.wellhead_pressure !== null ? String(record.wellhead_pressure) : "",
    tubing_pressure: record.tubing_pressure !== null ? String(record.tubing_pressure) : "",
    casing_pressure: record.casing_pressure !== null ? String(record.casing_pressure) : "",
    flowline_pressure: record.flowline_pressure !== null ? String(record.flowline_pressure) : "",
    wellhead_temperature: record.wellhead_temperature !== null ? String(record.wellhead_temperature) : "",
  };
}

export default function EditProductionRecordPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = Number(params.id);

  const [record, setRecord] = useState<ProductionEntry | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getProduction(id).then(setRecord).catch(() => setError("Unable to load this record."));
  }, [id]);

  async function handleSubmit(payload: ProductionPayload) {
    const updated = await updateProduction(id, payload);
    return { id: updated.id, warnings: updated.warnings };
  }

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title="Edit Production Record"
        description={record ? `${record.well_code} — ${record.record_date}` : "Loading…"}
      />
      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}
      {record ? (
        <ProductionForm
          initialValues={toFormValues(record)}
          submitLabel="Save Changes"
          lockWellAndDate
          onSubmit={handleSubmit}
          onSaved={(savedId) => router.push(`/production/records/${savedId}`)}
        />
      ) : null}
    </div>
  );
}
