import { PageHeader } from "@/components/layout/PageHeader";
import { KpiCard } from "@/components/dashboard/KpiCard";

export default function DashboardPage() {
  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title="Dashboard"
        description="Executive production overview. Values shown are placeholders pending live data integration."
      />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard label="Oil Production" value="—" unit="BOPD" hint="Not yet connected" />
        <KpiCard label="Gas Production" value="—" unit="MSCFD" hint="Not yet connected" />
        <KpiCard label="Water Production" value="—" unit="BWPD" hint="Not yet connected" />
        <KpiCard label="Producing Wells" value="—" hint="Not yet connected" />
        <KpiCard label="Target Variance" value="—" hint="Not yet connected" />
        <KpiCard label="Active Alerts" value="—" hint="Not yet connected" />
        <KpiCard label="Estimated Lost Production" value="—" unit="BOE/d" hint="Estimate, not yet connected" />
        <KpiCard label="Cost per Barrel" value="—" hint="Estimate, not yet connected" />
      </div>
      <div className="rounded-lg border border-dashed border-zinc-300 p-6 text-sm text-zinc-500 dark:border-zinc-700 dark:text-zinc-400">
        Top optimization opportunities will appear here once production and equipment data
        are connected. All AI-generated figures will be labeled as estimates requiring
        engineering review, never guaranteed conclusions.
      </div>
    </div>
  );
}
