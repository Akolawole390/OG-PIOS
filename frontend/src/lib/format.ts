export function formatLabel(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Formats a monetary value with its currency — falls back to a bare "$"-prefixed number
 * when the currency is unknown, since not every Production Loss estimate resolves one. */
export function formatCurrency(value: number | null | undefined, currency?: string | null): string {
  if (value === null || value === undefined) return "—";
  if (!currency) return `$${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency, maximumFractionDigits: 2 }).format(value);
  } catch {
    return `${value.toLocaleString(undefined, { maximumFractionDigits: 2 })} ${currency}`;
  }
}
