"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { ApiError, verifyEmail } from "@/lib/api";

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={null}>
      <VerifyEmailStatus />
    </Suspense>
  );
}

function VerifyEmailStatus() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";

  const [state, setState] = useState<"pending" | "success" | "error">(token ? "pending" : "error");
  const [error, setError] = useState<string | null>(token ? null : "This link is missing its verification token.");

  useEffect(() => {
    if (!token) return;
    verifyEmail(token)
      .then(() => setState("success"))
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : "Invalid or expired verification link.");
        setState("error");
      });
  }, [token]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-black">
      <div className="w-full max-w-sm rounded-lg border border-zinc-200 bg-white p-8 dark:border-zinc-800 dark:bg-zinc-950">
        <p className="text-xs font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-400">OG-PIOS</p>
        <h1 className="mt-1 text-lg font-semibold text-zinc-900 dark:text-zinc-50">Email verification</h1>

        {state === "pending" ? (
          <p className="mt-6 text-sm text-zinc-500 dark:text-zinc-400">Verifying…</p>
        ) : state === "success" ? (
          <p className="mt-6 text-sm text-zinc-700 dark:text-zinc-300">Your email has been verified.</p>
        ) : (
          <p className="mt-6 text-sm text-red-600 dark:text-red-400">{error}</p>
        )}

        <Link href="/login" className="mt-6 inline-block text-sm font-medium text-zinc-600 hover:underline dark:text-zinc-400">
          Back to sign in
        </Link>
      </div>
    </div>
  );
}
