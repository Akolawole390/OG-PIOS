"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { forgotPassword } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [debugResetUrl, setDebugResetUrl] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      const res = await forgotPassword(email);
      setMessage(res.message);
      setDebugResetUrl(res.debug_reset_url ?? null);
    } catch {
      // Same generic message even on an unexpected error — never signal whether the email exists.
      setMessage("If an account exists for that email, a password reset link has been sent.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-black">
      <div className="w-full max-w-sm rounded-lg border border-zinc-200 bg-white p-8 dark:border-zinc-800 dark:bg-zinc-950">
        <p className="text-xs font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-400">OG-PIOS</p>
        <h1 className="mt-1 text-lg font-semibold text-zinc-900 dark:text-zinc-50">Forgot password</h1>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          Enter your account email and we&apos;ll send you a reset link.
        </p>

        {message ? (
          <>
            <p className="mt-6 text-sm text-zinc-700 dark:text-zinc-300">{message}</p>
            {debugResetUrl ? (
              <div className="mt-4 rounded-md border border-dashed border-amber-400 bg-amber-50 p-3 text-xs text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200">
                <p className="font-medium">Development mode — no email service configured.</p>
                <p className="mt-1">
                  Reset link:{" "}
                  <a href={debugResetUrl} className="break-all underline">
                    {debugResetUrl}
                  </a>
                </p>
              </div>
            ) : null}
            <Link href="/login" className="mt-6 inline-block text-sm font-medium text-zinc-600 hover:underline dark:text-zinc-400">
              Back to sign in
            </Link>
          </>
        ) : (
          <form onSubmit={handleSubmit}>
            <label className="mt-6 block text-sm font-medium text-zinc-700 dark:text-zinc-300">
              Email
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-1 block w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
              />
            </label>

            <button
              type="submit"
              disabled={isSubmitting}
              className="mt-6 w-full rounded-md bg-amber-700 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-amber-800 disabled:opacity-50 dark:bg-amber-500 dark:text-zinc-950 dark:hover:bg-amber-400"
            >
              {isSubmitting ? "Sending…" : "Send reset link"}
            </button>

            <Link href="/login" className="mt-4 block text-center text-sm font-medium text-zinc-600 hover:underline dark:text-zinc-400">
              Back to sign in
            </Link>
          </form>
        )}
      </div>
    </div>
  );
}
