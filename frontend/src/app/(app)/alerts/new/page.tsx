"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import {
  createAlert,
  listEquipment,
  listFacilities,
  listWells,
  type AlertCategory,
  type AlertSeverity,
  type Equipment,
  type Facility,
  type Well,
} from "@/lib/api";

const CATEGORY_OPTIONS: AlertCategory[] = ["production", "equipment", "maintenance", "production_loss", "economics"];
const SEVERITY_OPTIONS: AlertSeverity[] = ["critical", "high", "medium", "low", "informational"];

export default function NewAlertPage() {
  const router = useRouter();
  const [category, setCategory] = useState<AlertCategory>("production");
  const [alertType, setAlertType] = useState("");
  const [severity, setSeverity] = useState<AlertSeverity>("medium");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [recommendedAction, setRecommendedAction] = useState("");
  const [fieldId, setFieldId] = useState("");
  const [wellId, setWellId] = useState("");
  const [equipmentId, setEquipmentId] = useState("");

  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [wells, setWells] = useState<Well[]>([]);
  const [equipmentOptions, setEquipmentOptions] = useState<Equipment[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    listFacilities().then(setFacilities).catch(() => undefined);
    listWells({ page_size: 100, sort: "well_id" }).then((res) => setWells(res.items)).catch(() => undefined);
    listEquipment({ page_size: 200, sort: "equipment_tag" }).then((res) => setEquipmentOptions(res.items)).catch(() => undefined);
  }, []);

  const fields = Array.from(new Map(facilities.map((f) => [f.field_id, f.field_name])).entries());

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (!alertType.trim() || !title.trim() || !description.trim()) {
      setError("Alert type, title, and description are required.");
      return;
    }
    setIsSubmitting(true);
    try {
      const alert = await createAlert({
        category,
        alert_type: alertType.trim(),
        severity,
        title: title.trim(),
        description: description.trim(),
        recommended_action: recommendedAction.trim() || null,
        field_id: fieldId ? Number(fieldId) : null,
        well_id: wellId ? Number(wellId) : null,
        equipment_id: equipmentId ? Number(equipmentId) : null,
      });
      router.push(`/alerts/${alert.id}`);
    } catch {
      setError("Unable to create this alert. Check the form and try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader title="Add Alert" description="Manually create an alert not otherwise caught by the rule engine." />

      <form onSubmit={handleSubmit} className="flex max-w-2xl flex-col gap-4">
        <div className="grid grid-cols-2 gap-4">
          <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
            Category
            <select value={category} onChange={(e) => setCategory(e.target.value as AlertCategory)} className={inputClass}>
              {CATEGORY_OPTIONS.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </label>
          <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
            Severity
            <select value={severity} onChange={(e) => setSeverity(e.target.value as AlertSeverity)} className={inputClass}>
              {SEVERITY_OPTIONS.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </label>
        </div>

        <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
          Alert Type
          <input value={alertType} onChange={(e) => setAlertType(e.target.value)} placeholder="e.g. manual_observation" className={inputClass} />
        </label>

        <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
          Title
          <input value={title} onChange={(e) => setTitle(e.target.value)} className={inputClass} />
        </label>

        <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
          Description
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} className={inputClass} />
        </label>

        <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
          Recommended Action
          <textarea value={recommendedAction} onChange={(e) => setRecommendedAction(e.target.value)} rows={2} className={inputClass} />
        </label>

        <div className="grid grid-cols-3 gap-4">
          <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
            Field
            <select value={fieldId} onChange={(e) => setFieldId(e.target.value)} className={inputClass}>
              <option value="">None</option>
              {fields.map(([id, name]) => (
                <option key={id} value={id}>{name}</option>
              ))}
            </select>
          </label>
          <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
            Well
            <select value={wellId} onChange={(e) => setWellId(e.target.value)} className={inputClass}>
              <option value="">None</option>
              {wells.map((w) => (
                <option key={w.id} value={w.id}>{w.well_id}</option>
              ))}
            </select>
          </label>
          <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
            Equipment
            <select value={equipmentId} onChange={(e) => setEquipmentId(e.target.value)} className={inputClass}>
              <option value="">None</option>
              {equipmentOptions.map((e) => (
                <option key={e.id} value={e.id}>{e.equipment_tag}</option>
              ))}
            </select>
          </label>
        </div>

        {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-fit rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
        >
          {isSubmitting ? "Saving…" : "Create Alert"}
        </button>
      </form>
    </div>
  );
}

const inputClass =
  "mt-1 block w-full rounded-md border border-zinc-300 px-3 py-2 text-sm disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900";
