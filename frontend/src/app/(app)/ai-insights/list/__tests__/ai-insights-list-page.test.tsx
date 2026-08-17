import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AiInsightsListPage from "@/app/(app)/ai-insights/list/page";
import * as api from "@/lib/api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/ai-insights/list",
}));

const mockInsight: api.InsightEntry = {
  id: 1,
  insight_type: "equipment_health_deterioration",
  category: "equipment",
  severity: "high",
  status: "new",
  generated_by: "rule_based",
  ai_provider: null,
  ai_model: null,
  ai_interpretation: null,
  title: "ESP-01 — Low Equipment Health",
  summary: "ESP-01's health score is 45.",
  recommended_investigation: "Schedule inspection.",
  data_quality_note: null,
  confidence_level: "high",
  estimated_production_impact_value: null,
  estimated_production_impact_unit: null,
  estimated_production_impact_note: null,
  estimated_financial_impact_value: null,
  estimated_financial_impact_currency: null,
  estimated_financial_impact_note: null,
  well_id: null,
  well_code: null,
  field_id: 1,
  field_name: "Field A",
  facility_id: null,
  facility_name: null,
  equipment_id: 1,
  equipment_tag: "ESP-01",
  maintenance_record_id: null,
  maintenance_work_order_number: null,
  production_loss_id: null,
  alert_id: null,
  dedup_key: "equipment_health_deterioration:equipment:1",
  occurrence_count: 1,
  generated_at: "2026-08-10T00:00:00Z",
  last_confirmed_at: "2026-08-10T00:00:00Z",
  is_stale: false,
  days_since_confirmed: 0,
  created_at: "2026-08-10T00:00:00Z",
  updated_at: "2026-08-10T00:00:00Z",
  disclaimer_text: "AI-generated estimate requiring engineering review; not a guaranteed conclusion.",
  evidence: [],
  feedback: [],
};

describe("AiInsightsListPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "listFacilities").mockResolvedValue([]);
    vi.spyOn(api, "listWells").mockResolvedValue({ items: [], total: 0, page: 1, page_size: 100 });
    vi.spyOn(api, "listEquipment").mockResolvedValue({ items: [], total: 0, page: 1, page_size: 200 });
  });

  it("renders insights in the table", async () => {
    vi.spyOn(api, "listInsights").mockResolvedValue({ items: [mockInsight], total: 1, page: 1, page_size: 25 });

    render(<AiInsightsListPage />);

    await waitFor(() => expect(screen.getByText("ESP-01 — Low Equipment Health")).toBeInTheDocument(), { timeout: 2000 });
    expect(screen.getByText("Field A / ESP-01")).toBeInTheDocument();
  });

  it("refetches with the search term after typing", async () => {
    const listInsightsSpy = vi
      .spyOn(api, "listInsights")
      .mockResolvedValue({ items: [mockInsight], total: 1, page: 1, page_size: 25 });

    render(<AiInsightsListPage />);
    await waitFor(() => expect(listInsightsSpy).toHaveBeenCalled(), { timeout: 2000 });

    fireEvent.change(screen.getByPlaceholderText(/search title\/summary/i), { target: { value: "ESP" } });

    await waitFor(
      () => expect(listInsightsSpy).toHaveBeenLastCalledWith(expect.objectContaining({ search: "ESP" })),
      { timeout: 2000 },
    );
  });

  it("shows an empty state when there are no insights", async () => {
    vi.spyOn(api, "listInsights").mockResolvedValue({ items: [], total: 0, page: 1, page_size: 25 });

    render(<AiInsightsListPage />);

    await waitFor(() => expect(screen.getByText("No insights found.")).toBeInTheDocument(), { timeout: 2000 });
  });
});
