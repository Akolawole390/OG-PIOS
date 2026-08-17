import type { GuardrailFlag } from "@/lib/api";

const SEVERITY_CLASS: Record<GuardrailFlag["severity"], string> = {
  error: "border-red-300 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950/40 dark:text-red-300",
  warning: "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300",
};

const SEVERITY_LABEL: Record<GuardrailFlag["severity"], string> = {
  error: "Invalid assumption",
  warning: "Unusual assumption",
};

/** Renders guardrail flags from a scenario run. `error` flags mean the assumption was
 * mathematically impossible (the API rejects these with a 422 before computing anything);
 * `warning` flags mean the assumption is valid but outside typical bounds — still computed and
 * shown, never silently dropped. */
export function GuardrailBanner({ flags }: { flags: GuardrailFlag[] }) {
  if (flags.length === 0) return null;

  return (
    <div className="flex flex-col gap-2">
      {flags.map((flag, index) => (
        <div key={`${flag.field}-${index}`} className={`rounded-md border p-3 text-sm ${SEVERITY_CLASS[flag.severity]}`}>
          <span className="font-medium">{SEVERITY_LABEL[flag.severity]} ({flag.field}): </span>
          {flag.message}
        </div>
      ))}
    </div>
  );
}
