import { PageHeader } from "@/components/layout/PageHeader";
import { ComingSoon } from "@/components/layout/ComingSoon";

export default function WhatIfSimulatorPage() {
  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title="What-If Simulator"
        description="Interactive scenario analysis. All outputs are labeled estimates."
      />
      <ComingSoon module="What-If Simulator" />
    </div>
  );
}
