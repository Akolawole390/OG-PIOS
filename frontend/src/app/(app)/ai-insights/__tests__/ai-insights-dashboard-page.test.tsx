import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AiInsightsPage from "@/app/(app)/ai-insights/page";
import * as api from "@/lib/api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/ai-insights",
}));

const mockInsight: api.InsightEntry = {
  id: 1,
  insight_type: "production_below_target",
  category: "production",
  severity: "critical",
  status: "new",
  generated_by: "rule_based",
  ai_provider: null,
  ai_model: null,
  ai_interpretation: null,
  title: "NDF-01-001 — Production Below Target",
  summary: "NDF-01-001 oil production is 38.3% below target.",
  recommended_investigation: "Review well performance and lift settings.",
  data_quality_note: null,
  confidence_level: "medium",
  estimated_production_impact_value: null,
  estimated_production_impact_unit: null,
  estimated_production_impact_note: null,
  estimated_financial_impact_value: null,
  estimated_financial_impact_currency: null,
  estimated_financial_impact_note: null,
  well_id: 1,
  well_code: "NDF-01-001",
  field_id: 1,
  field_name: "Niger Delta Field",
  facility_id: null,
  facility_name: null,
  equipment_id: null,
  equipment_tag: null,
  maintenance_record_id: null,
  maintenance_work_order_number: null,
  production_loss_id: null,
  alert_id: null,
  dedup_key: "production_below_target:well:1",
  occurrence_count: 1,
  generated_at: "2026-08-10T00:00:00Z",
  last_confirmed_at: "2026-08-10T00:00:00Z",
  is_stale: false,
  days_since_confirmed: 0,
  created_at: "2026-08-10T00:00:00Z",
  updated_at: "2026-08-10T00:00:00Z",
  disclaimer_text: "AI-generated estimate requiring engineering review; not a guaranteed conclusion.",
  evidence: [
    { id: 1, evidence_type: "observed_fact", description: "Production is below target.", source_type: "well", source_id: 1, source_label: "NDF-01-001", value: null, unit: null },
  ],
  feedback: [],
};

describe("AiInsightsPage (dashboard)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "getCurrentUser").mockResolvedValue({
      id: 1,
      email: "admin@ogpios.dev",
      full_name: "Admin",
      is_active: true,
      role_id: 1,
      role_name: "Administrator",
    });
    vi.spyOn(api, "getInsightSummary").mockResolvedValue({
      total: 5,
      open_count: 5,
      by_severity: { critical: 1, high: 1, medium: 1, low: 1, informational: 1 },
      by_category: [{ category: "production", count: 3 }],
      by_confidence: { high: 1, medium: 3, low: 1 },
      recent: [mockInsight],
      critical: [mockInsight],
      disclaimer_text: "AI-generated estimate requiring engineering review; not a guaranteed conclusion.",
    });
  });

  it("renders KPI counts, critical insights, and the disclaimer", async () => {
    render(<AiInsightsPage />);

    await waitFor(() => expect(screen.getByText("AI Insights")).toBeInTheDocument());
    expect(await screen.findAllByText("NDF-01-001 — Production Below Target")).not.toHaveLength(0);
    expect(
      screen.getByText("AI-generated estimate requiring engineering review; not a guaranteed conclusion.")
    ).toBeInTheDocument();
    expect(screen.getByText("Run Engine")).toBeInTheDocument();
  });

  it("hides the Run Engine button for a non-Administrator", async () => {
    vi.spyOn(api, "getCurrentUser").mockResolvedValue({
      id: 2,
      email: "analyst@ogpios.dev",
      full_name: "Analyst",
      is_active: true,
      role_id: 6,
      role_name: "Analyst",
    });

    render(<AiInsightsPage />);

    await waitFor(() => expect(screen.getByText("AI Insights")).toBeInTheDocument());
    await waitFor(() => expect(screen.queryByText("Run Engine")).not.toBeInTheDocument());
  });
});
