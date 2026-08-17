"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { NAV_ITEMS } from "@/config/navigation";
import { listWells, logout, type Well } from "@/lib/api";

const SIDEBAR_COLLAPSED_KEY = "og_pios_sidebar_collapsed";

export function Sidebar() {
  const pathname = usePathname();

  const [collapsed, setCollapsed] = useState(false);
  const [wellsExpanded, setWellsExpanded] = useState(false);
  const [wells, setWells] = useState<Well[] | null>(null);
  const [wellsLoading, setWellsLoading] = useState(false);
  const [wellsError, setWellsError] = useState(false);

  // Read the persisted preference after mount only — the server can't know it, and reading it
  // during the initial render would cause a hydration mismatch.
  useEffect(() => {
    setCollapsed(window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "true");
  }, []);

  function toggleCollapsed() {
    setCollapsed((prev) => {
      const next = !prev;
      window.localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(next));
      return next;
    });
  }

  // Wells are fetched once, lazily, the first time the submenu is expanded — never on mount,
  // since Sidebar renders before AuthGuard resolves and could otherwise fire one wasted
  // unauthenticated request on every page load.
  function toggleWells() {
    const next = !wellsExpanded;
    setWellsExpanded(next);
    if (next && wells === null && !wellsLoading) {
      setWellsLoading(true);
      setWellsError(false);
      listWells({ page_size: 100, sort: "well_id" })
        .then((res) => setWells(res.items))
        .catch(() => setWellsError(true))
        .finally(() => setWellsLoading(false));
    }
  }

  return (
    <nav
      aria-label="Primary"
      className={`flex h-full shrink-0 flex-col border-r border-zinc-200 bg-white transition-[width] dark:border-zinc-800 dark:bg-zinc-950 ${
        collapsed ? "w-14" : "w-64"
      }`}
    >
      <div className="flex items-center justify-between gap-2 px-3 py-5">
        {!collapsed ? (
          <div className="px-2">
            <span className="text-sm font-semibold tracking-wide text-amber-700 dark:text-amber-400">
              OG-PIOS
            </span>
            <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">
              Production Intelligence
            </p>
            <span
              className="mt-1.5 inline-block rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium tracking-wide text-amber-800 dark:bg-amber-900/40 dark:text-amber-300"
              title="This environment runs on synthetic demo data, not real field or company data."
            >
              PILOT · SYNTHETIC DATA
            </span>
          </div>
        ) : null}
        <button
          type="button"
          onClick={toggleCollapsed}
          aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
          aria-expanded={!collapsed}
          className="shrink-0 rounded-md p-1.5 text-sm font-medium text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-900 dark:hover:text-zinc-50"
        >
          {collapsed ? "›" : "‹"}
        </button>
      </div>

      <ul className="flex-1 space-y-0.5 overflow-y-auto px-3 pb-4">
        {NAV_ITEMS.map((item) => {
          const isActive =
            pathname === item.href || pathname.startsWith(`${item.href}/`);
          const isWells = item.href === "/wells";

          return (
            <li key={item.href}>
              <div className="flex items-center">
                <Link
                  href={item.href}
                  aria-current={isActive ? "page" : undefined}
                  title={collapsed ? item.label : undefined}
                  className={`block flex-1 truncate rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-amber-700 text-white dark:bg-amber-500 dark:text-zinc-950"
                      : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-900 dark:hover:text-zinc-50"
                  }`}
                >
                  {collapsed ? item.label.slice(0, 2).toUpperCase() : item.label}
                </Link>
                {isWells && !collapsed ? (
                  <button
                    type="button"
                    onClick={toggleWells}
                    aria-label={wellsExpanded ? "Collapse wells list" : "Expand wells list"}
                    aria-expanded={wellsExpanded}
                    className="shrink-0 rounded-md p-1.5 text-xs text-zinc-400 hover:bg-zinc-100 hover:text-zinc-900 dark:hover:bg-zinc-900 dark:hover:text-zinc-50"
                  >
                    {wellsExpanded ? "▾" : "▸"}
                  </button>
                ) : null}
              </div>

              {isWells && wellsExpanded && !collapsed ? (
                <ul className="mt-0.5 space-y-0.5 border-l border-zinc-200 pl-3 dark:border-zinc-800">
                  {wellsLoading ? (
                    <li className="px-3 py-1 text-xs text-zinc-400 dark:text-zinc-500">Loading…</li>
                  ) : wellsError ? (
                    <li className="px-3 py-1 text-xs text-red-500 dark:text-red-400">Unable to load wells.</li>
                  ) : (
                    (wells ?? []).map((well) => {
                      const href = `/wells/${well.id}`;
                      const wellActive = pathname === href;
                      return (
                        <li key={well.id}>
                          <Link
                            href={href}
                            aria-current={wellActive ? "page" : undefined}
                            className={`block truncate rounded-md px-3 py-1 text-xs transition-colors ${
                              wellActive
                                ? "bg-amber-700 text-white dark:bg-amber-500 dark:text-zinc-950"
                                : "text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-500 dark:hover:bg-zinc-900 dark:hover:text-zinc-50"
                            }`}
                          >
                            {well.well_id}
                          </Link>
                        </li>
                      );
                    })
                  )}
                </ul>
              ) : null}
            </li>
          );
        })}
      </ul>

      <div className="border-t border-zinc-200 px-3 py-3 dark:border-zinc-800">
        <Link
          href="/account/change-password"
          title={collapsed ? "Change Password" : undefined}
          className="block truncate rounded-md px-3 py-2 text-sm font-medium text-zinc-600 transition-colors hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-900 dark:hover:text-zinc-50"
        >
          {collapsed ? "CP" : "Change Password"}
        </Link>
        <button
          type="button"
          onClick={logout}
          title={collapsed ? "Log out" : undefined}
          className="block w-full truncate rounded-md px-3 py-2 text-left text-sm font-medium text-zinc-600 transition-colors hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-900 dark:hover:text-zinc-50"
        >
          {collapsed ? "⏻" : "Log out"}
        </button>
      </div>
    </nav>
  );
}
