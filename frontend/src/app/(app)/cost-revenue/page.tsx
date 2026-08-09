import { PageHeader } from "@/components/layout/PageHeader";
import { ComingSoon } from "@/components/layout/ComingSoon";

export default function CostRevenuePage() {
  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title="Cost & Revenue"
        description="Operating cost, revenue estimates, and cost-per-barrel analysis."
      />
      <ComingSoon module="Cost & Revenue" />
    </div>
  );
}
