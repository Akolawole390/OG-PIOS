import { PageHeader } from "@/components/layout/PageHeader";
import { ComingSoon } from "@/components/layout/ComingSoon";

export default function AiInsightsPage() {
  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title="AI Insights"
        description="Observations, possible contributors, and recommended investigations. Estimates only — not guaranteed conclusions."
      />
      <ComingSoon module="AI Insights" />
    </div>
  );
}
