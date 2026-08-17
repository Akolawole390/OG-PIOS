"use client";

import { useEffect, useState, type FormEvent } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { AdminGuard } from "@/components/administration/AdminGuard";
import { formatLabel } from "@/lib/format";
import { listSettings, updateSetting, type SystemSetting } from "@/lib/api";

const DISPLAY_KEYS = new Set([
  "company_name",
  "default_currency",
  "unit_system",
  "date_format",
  "timezone",
  "default_production_unit",
  "default_gas_unit",
  "default_volume_unit",
]);

function groupOf(key: string): string {
  if (DISPLAY_KEYS.has(key)) return "Company & Display Settings";
  if (key.startsWith("alert_")) return "Alert Thresholds";
  if (key.startsWith("insight_")) return "AI Insight Thresholds";
  if (key.startsWith("whatif_")) return "What-If Simulator Thresholds";
  return "General Operational Settings";
}

const GROUP_ORDER = [
  "Company & Display Settings",
  "General Operational Settings",
  "Alert Thresholds",
  "AI Insight Thresholds",
  "What-If Simulator Thresholds",
];

export default function AdministrationSettingsPage() {
  const [settings, setSettings] = useState<SystemSetting[]>([]);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [savedKey, setSavedKey] = useState<string | null>(null);
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [errorKey, setErrorKey] = useState<string | null>(null);
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
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>, key: string) {
    event.preventDefault();
    setError(null);
    setErrorKey(null);
    setSavedKey(null);
    setSavingKey(key);
    try {
      await updateSetting(key, draft[key]);
      setSavedKey(key);
      refresh();
    } catch {
      setErrorKey(key);
    } finally {
      setSavingKey(null);
    }
  }

  const grouped = new Map<string, SystemSetting[]>();
  for (const setting of settings) {
    const group = groupOf(setting.key);
    const list = grouped.get(group) ?? [];
    list.push(setting);
    grouped.set(group, list);
  }

  return (
    <AdminGuard>
      <div className="flex flex-1 flex-col gap-6">
        <PageHeader
          title="System Settings"
          description="Company/display defaults and operational alert thresholds. All values are validated server-side before being saved."
        />

        {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

        {GROUP_ORDER.filter((g) => grouped.has(g)).map((group) => (
          <div key={group}>
            <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-50">{group}</h3>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {(grouped.get(group) ?? []).map((setting) => (
                <form
                  key={setting.key}
                  onSubmit={(e) => handleSubmit(e, setting.key)}
                  className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950"
                >
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                    {formatLabel(setting.key)}
                    <input
                      value={draft[setting.key] ?? ""}
                      onChange={(e) => setDraft((prev) => ({ ...prev, [setting.key]: e.target.value }))}
                      className="mt-1 block w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                    />
                  </label>
                  {setting.description ? (
                    <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{setting.description}</p>
                  ) : null}
                  {errorKey === setting.key ? (
                    <p className="mt-1 text-xs text-red-600 dark:text-red-400">Value rejected — check the allowed format.</p>
                  ) : null}
                  {savedKey === setting.key ? (
                    <p className="mt-1 text-xs text-green-700 dark:text-green-400">Saved.</p>
                  ) : null}
                  <button
                    type="submit"
                    disabled={savingKey === setting.key}
                    className="mt-3 rounded-md bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
                  >
                    {savingKey === setting.key ? "Saving…" : "Save"}
                  </button>
                </form>
              ))}
            </div>
          </div>
        ))}
      </div>
    </AdminGuard>
  );
}
