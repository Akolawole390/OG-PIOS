"use client";

import { useEffect, useState, type ReactNode } from "react";
import { getCurrentUser } from "@/lib/api";

/** Client-side courtesy gate only — every `/administration/*` and admin-only `/users` endpoint
 * already enforces `require_role("Administrator")` server-side regardless of this component.
 * This exists purely so a non-Administrator sees a clear message instead of a page full of
 * failed requests. */
export function AdminGuard({ children }: { children: ReactNode }) {
  const [state, setState] = useState<"loading" | "allowed" | "denied">("loading");

  useEffect(() => {
    getCurrentUser()
      .then((user) => setState(user.role_name === "Administrator" ? "allowed" : "denied"))
      .catch(() => setState("denied"));
  }, []);

  if (state === "loading") return null;

  if (state === "denied") {
    return (
      <div className="rounded-lg border border-dashed border-zinc-300 p-6 text-sm text-zinc-500 dark:border-zinc-700 dark:text-zinc-400">
        <p className="font-medium text-zinc-700 dark:text-zinc-300">Access restricted</p>
        <p className="mt-1">Administration is available to Administrator accounts only.</p>
      </div>
    );
  }

  return <>{children}</>;
}
