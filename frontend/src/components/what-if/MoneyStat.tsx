import { MultiCurrencyAmount } from "@/components/cost-revenue/MultiCurrencyAmount";
import type { MoneyByCurrency } from "@/lib/api";

type MoneyStatProps = {
  label: string;
  amounts: MoneyByCurrency[];
  hint?: string;
  calculated?: boolean;
};

/** Same shape as KpiCard, but for currency-grouped money figures (which KpiCard's plain
 * `value: string` can't express) — mirrors the local MoneyStat pattern already used on the
 * Cost & Revenue dashboard. */
export function MoneyStat({ label, amounts, hint, calculated = true }: MoneyStatProps) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex items-center gap-1.5">
        <p className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">{label}</p>
        {calculated ? (
          <span className="rounded border border-zinc-300 px-1 text-[10px] font-medium uppercase tracking-wide text-zinc-400 dark:border-zinc-700 dark:text-zinc-500">
            Estimate
          </span>
        ) : null}
      </div>
      <p className="mt-2 text-xl font-semibold text-zinc-900 dark:text-zinc-50">
        <MultiCurrencyAmount amounts={amounts} />
      </p>
      {hint ? <p className="mt-1 text-xs text-zinc-400 dark:text-zinc-500">{hint}</p> : null}
    </div>
  );
}
