import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import InsightDetailPage from "@/app/(app)/ai-insights/[id]/page";
import * as api from "@/lib/api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/ai-insights/1",
  useParams: () => ({ id: "1" }),
  useRouter: () => ({ push: vi.fn() }),
}));

const mockInsight: api.InsightEntry = {
  id: 1,
  insight_type: "equipment_production_maintenance_downtime_correlation",
  category: "cross_domain",
  severity: "high",
  status: "new",
  generated_by: "rule_based",
  ai_provider: null,
  ai_model: null,
  ai_interpretation: null,
  title: "NDF-01-001 — Possible Equipment-Related Production Issue",
  summary: "Production declined while equipment health deteriorated.",
  recommended_investigation: "Review ESP-01's operating history and recent maintenance records.",
  data_quality_note: null,
  confidence_level: "high",
  estimated_production_impact_value: 500,
  estimated_production_impact_unit: "bbl",
  estimated_production_impact_note: "Estimated lost production.",
  estimated_financial_impact_value: 35000,
  estimated_financial_impact_currency: "USD",
  estimated_financial_impact_note: "Estimated revenue impact.",
  well_id: 1,
  well_code: "NDF-01-001",
  field_id: 1,
  field_name: "Niger Delta Field",
  facility_id: null,
  facility_name: null,
  equipment_id: 1,
  equipment_tag: "ESP-01",
  maintenance_record_id: null,
  maintenance_work_order_number: null,
  production_loss_id: null,
  alert_id: null,
  dedup_key: "equipment_production_maintenance_downtime_correlation:well_equipment:1:1",
  occurrence_count: 1,
  generated_at: "2026-08-10T00:00:00Z",
  last_confirmed_at: "2026-08-10T00:00:00Z",
  is_stale: false,
  days_since_confirmed: 0,
  created_at: "2026-08-10T00:00:00Z",
  updated_at: "2026-08-10T00:00:00Z",
  disclaimer_text: "AI-generated estimate requiring engineering review; not a guaranteed conclusion.",
  evidence: [
    { id: 1, evidence_type: "observed_fact", description: "Production declined 18%.", source_type: "well", source_id: 1, source_label: "NDF-01-001", value: null, unit: null },
    { id: 2, evidence_type: "calculated_metric", description: "ESP-01 health score dropped to 46.", source_type: "equipment", source_id: 1, source_label: "ESP-01", value: 46, unit: "score" },
    { id: 3, evidence_type: "possible_contributor", description: "2 maintenance events in the last 90 days.", source_type: "maintenance_record", source_id: 5, source_label: "WO-000005", value: 2, unit: "events" },
  ],
  feedback: [],
};

describe("InsightDetailPage", () => {
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
    vi.spyOn(api, "getInsight").mockResolvedValue(mockInsight);
  });

  it("renders summary, grouped evidence, impact, and related records", async () => {
    render(<InsightDetailPage />);

    await waitFor(() => expect(screen.getAllByText("NDF-01-001 — Possible Equipment-Related Production Issue").length).toBeGreaterThan(0));
    expect(screen.getByText("Observed Facts")).toBeInTheDocument();
    expect(screen.getByText("Calculated Metrics")).toBeInTheDocument();
    expect(screen.getByText("Possible Contributors")).toBeInTheDocument();
    expect(screen.getByText("500 bbl")).toBeInTheDocument();
    expect(screen.getByText(/USD 35,000/)).toBeInTheDocument();
    expect(screen.getByText("Mark Reviewed")).toBeInTheDocument();
  });

  it("marks the insight reviewed and reloads", async () => {
    const statusSpy = vi.spyOn(api, "updateInsightStatus").mockResolvedValue({ ...mockInsight, status: "reviewed" });

    render(<InsightDetailPage />);
    await waitFor(() => expect(screen.getAllByText(/Possible Equipment-Related Production Issue/).length).toBeGreaterThan(0));

    fireEvent.click(screen.getByRole("button", { name: /mark reviewed/i }));

    await waitFor(() => expect(statusSpy).toHaveBeenCalledWith(1, "reviewed"));
  });

  it("hides action buttons for a Viewer", async () => {
    vi.spyOn(api, "getCurrentUser").mockResolvedValue({
      id: 2,
      email: "viewer@ogpios.dev",
      full_name: "Viewer",
      is_active: true,
      role_id: 7,
      role_name: "Viewer",
    });

    render(<InsightDetailPage />);

    await waitFor(() => expect(screen.getAllByText(/Possible Equipment-Related Production Issue/).length).toBeGreaterThan(0));
    expect(screen.queryByText("Mark Reviewed")).not.toBeInTheDocument();
  });
});
