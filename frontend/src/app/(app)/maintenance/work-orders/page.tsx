"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { MaintenanceTable } from "@/components/maintenance/MaintenanceTable";
import { getCurrentUser, listMaintenance, type CurrentUser, type MaintenanceEntry } from "@/lib/api";

const ACTIVE_STATUSES = new Set(["scheduled", "open", "in_progress", "waiting_for_parts"]);
const CAN_MANAGE = new Set(["Administrator", "Maintenance Engineer"]);

export default function WorkOrdersPage() {
  const [items, setItems] = useState<MaintenanceEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);

  useEffect(() => {
    getCurrentUser().then(setCurrentUser).catch(() => undefined);
  }, []);

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    listMaintenance({ page_size: 200, sort: "planned_completion_date", order: "asc" })
      .then((res) => setItems(res.items.filter((item) => ACTIVE_STATUSES.has(item.status))))
      .catch(() => setError("Unable to load work orders. Try again."))
      .finally(() => setIsLoading(false));
  }, []);

  const canManage = currentUser ? CAN_MANAGE.has(currentUser.role_name) : false;

  return (
    <div className="flex flex-1 flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <PageHeader
          title="Work Orders"
          description="Active maintenance work: scheduled, open, in progress, or waiting on parts."
        />
        {canManage ? (
          <Link
            href="/maintenance/new"
            className="shrink-0 rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
          >
            Create Work Order
          </Link>
        ) : null}
      </div>

      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

      <MaintenanceTable items={items} isLoading={isLoading} emptyMessage="No active work orders." />
    </div>
  );
}
