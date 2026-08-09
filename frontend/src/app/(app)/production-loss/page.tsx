import { PageHeader } from "@/components/layout/PageHeader";
import { ComingSoon } from "@/components/layout/ComingSoon";

export default function ProductionLossPage() {
  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title="Production Loss"
        description="Estimated production loss from downtime, constraints, and decline events."
      />
      <ComingSoon module="Production Loss" />
    </div>
  );
}
