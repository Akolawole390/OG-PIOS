"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV_ITEMS } from "@/config/navigation";

export function Sidebar() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Primary"
      className="flex h-full w-64 shrink-0 flex-col border-r border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950"
    >
      <div className="px-5 py-5">
        <span className="text-sm font-semibold tracking-wide text-zinc-900 dark:text-zinc-50">
          OG-PIOS
        </span>
        <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">
          Production Intelligence
        </p>
      </div>
      <ul className="flex-1 space-y-0.5 overflow-y-auto px-3 pb-4">
        {NAV_ITEMS.map((item) => {
          const isActive =
            pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={isActive ? "page" : undefined}
                className={`block rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                    : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-900 dark:hover:text-zinc-50"
                }`}
              >
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
