import { type MoneyByCurrency } from "@/lib/api";
import { formatCurrency } from "@/lib/format";

type MultiCurrencyAmountProps = {
  amounts: MoneyByCurrency[];
  /** Shown when the list is empty — distinguishes "genuinely zero" from "not computable"
   * contexts. Defaults to an em dash. */
  emptyLabel?: string;
};

/**
 * Renders a currency-grouped amount list (never blended into one number) as e.g.
 * "$45,000.00 · ₦12,000,000.00" — the one shared primitive every money figure in this module
 * goes through, since amounts in different currencies are never summed without an explicit
 * exchange rate (none exists in this app).
 */
export function MultiCurrencyAmount({ amounts, emptyLabel = "—" }: MultiCurrencyAmountProps) {
  if (amounts.length === 0) {
    return <span>{emptyLabel}</span>;
  }
  return (
    <span>
      {amounts.map((m, index) => (
        <span key={m.currency}>
          {index > 0 ? " · " : ""}
          {formatCurrency(m.amount, m.currency)}
        </span>
      ))}
    </span>
  );
}
