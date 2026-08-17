"use client";

import type { ScenarioAssumptions } from "@/lib/api";

type AssumptionFormProps = {
  values: ScenarioAssumptions;
  onChange: (values: ScenarioAssumptions) => void;
  disabled?: boolean;
};

type FieldConfig = {
  key: keyof ScenarioAssumptions;
  label: string;
  hint?: string;
};

// Grouped to mirror the module spec's own "Production / Downtime / Production Loss / Cost /
// Commodity Price" scenario-variable sections — every field optional; blank means "no change."
const GROUPS: { title: string; fields: FieldConfig[] }[] = [
  {
    title: "Production",
    fields: [
      { key: "production_change_pct", label: "Production Change (%)", hint: "e.g. 10 for +10%, -15 for -15%" },
    ],
  },
  {
    title: "Downtime",
    fields: [
      {
        key: "downtime_change_pct",
        label: "Downtime Change (%)",
        hint: "Negative = less downtime, e.g. -20 for a 20% reduction. Recovered production is shown separately, as an estimate.",
      },
    ],
  },
  {
    title: "Production Loss",
    fields: [
      {
        key: "production_loss_reduction_pct",
        label: "Production Loss Reduction (%)",
        hint: "0-100. e.g. 25 for an estimated 25% reduction in production loss.",
      },
    ],
  },
  {
    title: "Cost",
    fields: [
      { key: "operating_cost_change_pct", label: "Operating Cost Change (%)" },
      {
        key: "energy_cost_change_pct",
        label: "Energy Cost Change (%)",
        hint: "Applies only to the energy portion of operating cost, on top of Operating Cost Change.",
      },
      { key: "maintenance_cost_change_pct", label: "Maintenance Cost Change (%)" },
    ],
  },
  {
    title: "Commodity Price",
    fields: [
      { key: "oil_price_override", label: "Oil Price Override ($/bbl)", hint: "Overrides the current price outright." },
      { key: "oil_price_change_pct", label: "Oil Price Change (%)", hint: "Ignored if Oil Price Override is set." },
      { key: "gas_price_override", label: "Gas Price Override ($/mscf)", hint: "Overrides the current price outright." },
      { key: "gas_price_change_pct", label: "Gas Price Change (%)", hint: "Ignored if Gas Price Override is set." },
    ],
  },
];

const inputClass =
  "mt-1 block w-full rounded-md border border-zinc-300 px-3 py-2 text-sm disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900";

/** Scenario Builder's assumption inputs — every field is optional and defaults to "no change,"
 * so a scenario can test a single lever (e.g. only downtime) without having to zero out every
 * other variable. Designed so a future scenario variable is just one more entry in GROUPS,
 * never a redesign of this component. */
export function AssumptionForm({ values, onChange, disabled }: AssumptionFormProps) {
  function update(key: keyof ScenarioAssumptions, raw: string) {
    if (raw.trim() === "") {
      onChange({ ...values, [key]: null });
      return;
    }
    const parsed = Number(raw);
    onChange({ ...values, [key]: Number.isNaN(parsed) ? null : parsed });
  }

  return (
    <div className="flex flex-col gap-5">
      {GROUPS.map((group) => (
        <div key={group.title}>
          <h4 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            {group.title}
          </h4>
          <div className="mt-2 grid grid-cols-1 gap-4 sm:grid-cols-2">
            {group.fields.map((field) => (
              <label key={field.key} className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                {field.label}
                <input
                  type="number"
                  step="any"
                  disabled={disabled}
                  placeholder="No change"
                  value={values[field.key] ?? ""}
                  onChange={(e) => update(field.key, e.target.value)}
                  className={inputClass}
                />
                {field.hint ? (
                  <span className="mt-1 block text-xs font-normal text-zinc-400 dark:text-zinc-500">{field.hint}</span>
                ) : null}
              </label>
            ))}
          </div>
        </div>
      ))}
      <p className="text-xs text-zinc-500 dark:text-zinc-400">
        Leave any field blank for &ldquo;no change.&rdquo; Values well outside typical ranges are still computed but
        flagged as outside configured operating assumptions — they are never silently rejected.
      </p>
    </div>
  );
}
