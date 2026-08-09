"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const body = new URLSearchParams({ username: email, password });
      const response = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body,
      });

      if (!response.ok) {
        throw new Error("Invalid email or password.");
      }

      const data = (await response.json()) as { access_token: string };
      // Scaffold-only: localStorage is a placeholder until httpOnly cookie auth is implemented.
      window.localStorage.setItem("og_pios_token", data.access_token);
      router.push("/dashboard");
    } catch {
      setError("Unable to sign in. Check your credentials and try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-black">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm rounded-lg border border-zinc-200 bg-white p-8 dark:border-zinc-800 dark:bg-zinc-950"
      >
        <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
          OG-PIOS
        </h1>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          Sign in to your account
        </p>

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

        <label className="mt-4 block text-sm font-medium text-zinc-700 dark:text-zinc-300">
          Password
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 block w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          />
        </label>

        {error ? (
          <p className="mt-4 text-sm text-red-600 dark:text-red-400">{error}</p>
        ) : null}

        <button
          type="submit"
          disabled={isSubmitting}
          className="mt-6 w-full rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
        >
          {isSubmitting ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
