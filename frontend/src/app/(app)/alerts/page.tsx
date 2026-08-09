import { PageHeader } from "@/components/layout/PageHeader";
import { ComingSoon } from "@/components/layout/ComingSoon";

export default function AlertsPage() {
  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title="Alerts"
        description="Production, equipment, and maintenance alerts by severity and state."
      />
      <ComingSoon module="Alerts" />
    </div>
  );
}
