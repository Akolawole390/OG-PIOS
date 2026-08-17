"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { ScheduleItemList } from "@/components/maintenance/ScheduleItemList";
import { getMaintenanceSchedule, type MaintenanceScheduleResponse } from "@/lib/api";

export default function OverdueMaintenancePage() {
  const [schedule, setSchedule] = useState<MaintenanceScheduleResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMaintenanceSchedule().then(setSchedule).catch(() => setError("Unable to load overdue maintenance."));
  }, []);

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title="Overdue Maintenance"
        description={
          schedule
            ? `${schedule.overdue.length} item(s) overdue as of ${schedule.reference_date}.`
            : "Work orders and equipment past their planned/next maintenance date."
        }
      />

      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

      <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
        <ScheduleItemList items={schedule?.overdue ?? []} emptyMessage="Nothing overdue — good shape." />
      </div>
    </div>
  );
}
