type PageHeaderProps = {
  title: string;
  description?: string;
};

export function PageHeader({ title, description }: PageHeaderProps) {
  return (
    <div className="border-b border-zinc-200 pb-4 dark:border-zinc-800">
      <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">
        {title}
      </h1>
      {description ? (
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          {description}
        </p>
      ) : null}
    </div>
  );
}
