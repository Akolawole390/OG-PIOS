import { PageHeader } from "@/components/layout/PageHeader";
import { ComingSoon } from "@/components/layout/ComingSoon";

export default function EquipmentPage() {
  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title="Equipment"
        description="Equipment inventory and health monitoring."
      />
      <ComingSoon module="Equipment" />
    </div>
  );
}
