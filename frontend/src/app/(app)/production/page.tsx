import { PageHeader } from "@/components/layout/PageHeader";
import { ComingSoon } from "@/components/layout/ComingSoon";

export default function ProductionPage() {
  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title="Production"
        description="Production data entry, review, and analytics."
      />
      <ComingSoon module="Production" />
    </div>
  );
}
