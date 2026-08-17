"use client";

import Link from "next/link";
import { type MaintenanceScheduleItem } from "@/lib/api";
import { MaintenancePriorityBadge, MaintenanceStatusBadge } from "@/components/maintenance/MaintenanceTable";

type ScheduleItemListProps = {
  items: MaintenanceScheduleItem[];
  emptyMessage: string;
};

function hrefFor(item: MaintenanceScheduleItem): string {
  return item.source === "work_order" ? `/maintenance/${item.id}` : `/equipment/${item.id}`;
}

function dueLabel(item: MaintenanceScheduleItem): string {
  if (item.days_from_today === 0) return "Due today";
  if (item.days_from_today < 0) return `${Math.abs(item.days_from_today)} day${item.days_from_today === -1 ? "" : "s"} overdue`;
  return `In ${item.days_from_today} day${item.days_from_today === 1 ? "" : "s"}`;
}

export function ScheduleItemList({ items, emptyMessage }: ScheduleItemListProps) {
  if (items.length === 0) {
    return <p className="text-sm text-zinc-500 dark:text-zinc-400">{emptyMessage}</p>;
  }

  return (
    <ul className="space-y-2 text-sm">
      {items.map((item) => (
        <li
          key={`${item.source}-${item.id}`}
          className="flex items-center justify-between gap-3 rounded-md border border-zinc-100 px-3 py-2 dark:border-zinc-900"
        >
          <div>
            <Link href={hrefFor(item)} className="font-medium text-zinc-900 hover:underline dark:text-zinc-50">
              {item.label}
            </Link>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              {item.due_date} · {dueLabel(item)}
              {item.source === "equipment" ? " · from equipment's next maintenance date" : ""}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {item.priority ? <MaintenancePriorityBadge priority={item.priority} /> : null}
            {item.status ? <MaintenanceStatusBadge status={item.status} /> : null}
          </div>
        </li>
      ))}
    </ul>
  );
}
