import { PageHeader } from "@/components/layout/PageHeader";
import { ComingSoon } from "@/components/layout/ComingSoon";

export default function ReportsPage() {
  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title="Reports"
        description="Daily, weekly, and monthly production and operations reports."
      />
      <ComingSoon module="Reports" />
    </div>
  );
}
