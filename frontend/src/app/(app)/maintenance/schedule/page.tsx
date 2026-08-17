"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { ScheduleItemList } from "@/components/maintenance/ScheduleItemList";
import { getMaintenanceSchedule, type MaintenanceScheduleResponse } from "@/lib/api";

export default function MaintenanceSchedulePage() {
  const [schedule, setSchedule] = useState<MaintenanceScheduleResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMaintenanceSchedule().then(setSchedule).catch(() => setError("Unable to load the maintenance schedule."));
  }, []);

  return (
    <div className="flex flex-1 flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <PageHeader
          title="Maintenance Schedule"
          description={
            schedule
              ? `As of ${schedule.reference_date} — upcoming window: ${schedule.lookahead_days} days.`
              : "Overdue, due-today, and upcoming maintenance."
          }
        />
        <Link
          href="/maintenance/overdue"
          className="shrink-0 rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
        >
          Overdue Only
        </Link>
      </div>

      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

      <p className="text-xs text-zinc-500 dark:text-zinc-400">
        Rule-based scheduling view combining open work orders&apos; planned completion dates and each
        equipment&apos;s own next-maintenance-due date — not automatic status changes.
      </p>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h3 className="text-sm font-semibold text-red-700 dark:text-red-400">
            Overdue ({schedule?.overdue.length ?? 0})
          </h3>
          <div className="mt-3">
            <ScheduleItemList items={schedule?.overdue ?? []} emptyMessage="Nothing overdue." />
          </div>
        </div>
        <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h3 className="text-sm font-semibold text-amber-700 dark:text-amber-400">
            Due Today ({schedule?.due_today.length ?? 0})
          </h3>
          <div className="mt-3">
            <ScheduleItemList items={schedule?.due_today ?? []} emptyMessage="Nothing due today." />
          </div>
        </div>
        <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">
            Upcoming ({schedule?.upcoming.length ?? 0})
          </h3>
          <div className="mt-3">
            <ScheduleItemList items={schedule?.upcoming ?? []} emptyMessage="Nothing upcoming." />
          </div>
        </div>
      </div>
    </div>
  );
}
