export function ComingSoon({ module }: { module: string }) {
  return (
    <div className="flex flex-1 items-center justify-center rounded-lg border border-dashed border-zinc-300 py-24 dark:border-zinc-700">
      <div className="text-center">
        <p className="text-sm font-medium text-zinc-900 dark:text-zinc-50">
          {module} — Coming soon
        </p>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          This module is scaffolded but not yet implemented.
        </p>
      </div>
    </div>
  );
}
