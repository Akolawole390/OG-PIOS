import { PageHeader } from "@/components/layout/PageHeader";
import { ComingSoon } from "@/components/layout/ComingSoon";

export default function WellsPage() {
  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title="Wells"
        description="Well identification, production, pressure, and history."
      />
      <ComingSoon module="Wells" />
    </div>
  );
}
