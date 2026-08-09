import { PageHeader } from "@/components/layout/PageHeader";
import { ComingSoon } from "@/components/layout/ComingSoon";

export default function MaintenancePage() {
  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title="Maintenance"
        description="Preventive, corrective, and emergency maintenance records."
      />
      <ComingSoon module="Maintenance" />
    </div>
  );
}
