import Link from "next/link";
import type { EquipmentInvestigationItem } from "@/lib/api";

const BAND_STYLES: Record<string, string> = {
  excellent: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  good: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  monitor: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  "maintenance required": "bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300",
  critical: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
};

function bandStyle(band: string | null): string {
  if (!band) return "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300";
  return BAND_STYLES[band.toLowerCase()] ?? "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300";
}

export function EquipmentHealthList({ items }: { items: EquipmentInvestigationItem[] }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Equipment Requiring Attention</h3>
      {items.length === 0 ? (
        <p className="mt-3 text-sm text-zinc-500 dark:text-zinc-400">No equipment currently flagged.</p>
      ) : (
        <ul className="mt-3 flex flex-col gap-2.5">
          {items.slice(0, 6).map((item) => (
            <li key={item.id} className="flex items-start justify-between gap-2 text-sm">
              <Link href={`/equipment/${item.id}`} className="truncate text-zinc-700 hover:underline dark:text-zinc-300">
                {item.equipment_tag} — {item.name}
              </Link>
              <span className={`shrink-0 inline-block rounded-full px-2 py-0.5 text-xs font-medium ${bandStyle(item.health_band)}`}>
                {item.health_band ?? "Unscored"}
              </span>
            </li>
          ))}
        </ul>
      )}
      <Link href="/equipment" className="mt-3 inline-block text-xs font-medium text-zinc-600 hover:underline dark:text-zinc-400">
        View all equipment →
      </Link>
    </div>
  );
}
