"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { PageHeader } from "@/components/layout/PageHeader";
import { WellForm, type WellFormValues } from "@/components/wells/WellForm";
import { getWell, updateWell, type Well, type WellPayload } from "@/lib/api";

function toFormValues(well: Well): Partial<WellFormValues> {
  return {
    well_id: well.well_id,
    name: well.name,
    well_type: well.well_type ?? "",
    status: well.status,
    artificial_lift_type: well.artificial_lift_type ?? "",
    latitude: well.latitude !== null ? String(well.latitude) : "",
    longitude: well.longitude !== null ? String(well.longitude) : "",
    facility_id: String(well.facility_id),
    completion_date: well.completion_date ?? "",
    completion_type: well.completion_type ?? "",
    total_depth_ft: well.total_depth_ft !== null ? String(well.total_depth_ft) : "",
  };
}

export default function EditWellPage() {
  const params = useParams<{ wellId: string }>();
  const router = useRouter();
  const wellId = Number(params.wellId);

  const [well, setWell] = useState<Well | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getWell(wellId)
      .then(setWell)
      .catch(() => setError("Unable to load this well."));
  }, [wellId]);

  async function handleSubmit(payload: WellPayload) {
    const updated = await updateWell(wellId, payload);
    router.push(`/wells/${updated.id}`);
  }

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader title="Edit Well" description={well ? well.name : "Loading…"} />
      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}
      {well ? (
        <WellForm initialValues={toFormValues(well)} submitLabel="Save Changes" onSubmit={handleSubmit} />
      ) : null}
    </div>
  );
}
