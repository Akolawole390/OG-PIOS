"use client";

import { useEffect, useState, type FormEvent } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { getCurrentUser, listSettings, updateSetting, type CurrentUser, type SystemSetting } from "@/lib/api";

export default function ProductionSettingsPage() {
  const [settings, setSettings] = useState<SystemSetting[]>([]);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [savedMessage, setSavedMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function refresh() {
    listSettings()
      .then((res) => {
        setSettings(res);
        setDraft(Object.fromEntries(res.map((s) => [s.key, s.value])));
      })
      .catch(() => setError("Unable to load settings."));
  }

  useEffect(() => {
    refresh();
    getCurrentUser().then(setCurrentUser).catch(() => undefined);
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>, key: string) {
    event.preventDefault();
    setError(null);
    setSavedMessage(null);
    try {
      await updateSetting(key, draft[key]);
      setSavedMessage(`${key} updated.`);
      refresh();
    } catch {
      setError("Unable to save this setting. Value must be numeric and positive.");
    }
  }

  const isAdministrator = currentUser?.role_name === "Administrator";

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title="Production Settings"
        description="System-wide configuration, e.g. the BOE gas conversion factor used across all production KPIs."
      />

      {!isAdministrator ? (
        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          You can view these settings, but only an Administrator can change them.
        </p>
      ) : null}

      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}
      {savedMessage ? <p className="text-sm text-green-700 dark:text-green-400">{savedMessage}</p> : null}

      <div className="flex flex-col gap-4">
        {settings.map((setting) => (
          <form
            key={setting.key}
            onSubmit={(e) => handleSubmit(e, setting.key)}
            className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950"
          >
            <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
              {setting.key}
              <input
                value={draft[setting.key] ?? ""}
                disabled={!isAdministrator}
                onChange={(e) => setDraft((prev) => ({ ...prev, [setting.key]: e.target.value }))}
                className="mt-1 block w-full max-w-xs rounded-md border border-zinc-300 px-3 py-2 text-sm disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900"
              />
            </label>
            {setting.description ? (
              <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{setting.description}</p>
            ) : null}
            {isAdministrator ? (
              <button
                type="submit"
                className="mt-3 rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
              >
                Save
              </button>
            ) : null}
          </form>
        ))}
      </div>
    </div>
  );
}
