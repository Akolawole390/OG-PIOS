import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DashboardPage from "@/app/(app)/dashboard/page";
import * as api from "@/lib/api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
}));

const productionKpis: api.ProductionKpis = {
  total_oil_bbl: 12500,
  total_gas_mscf: 8400,
  total_water_bbl: 3200,
  avg_daily_oil_bopd: 1250,
  avg_daily_gas_mscfd: 840,
  avg_daily_water_bwpd: 320,
  avg_water_cut_pct: 12.5,
  avg_gor: 672,
  boe: 13900,
  boe_gas_factor: 6000,
  producing_wells_count: 18,
  target_oil_bopd: 1300,
  target_variance_pct: -3.8,
  reference_date: "2026-08-14",
  days_in_range: 10,
};

const alertSummary: api.AlertSummaryResponse = {
  total: 12,
  open_count: 4,
  by_severity: { critical: 1, high: 2, medium: 1, low: 0, informational: 0 },
  by_status: { new: 2, acknowledged: 2, investigating: 0, resolved: 6, dismissed: 2 },
  by_category: [],
  by_field: [],
  by_equipment: [],
  recent: [
    {
      id: 1, alert_type: "production_decline", category: "production", source_module: "production", severity: "critical",
      status: "new", title: "Well NDF-01-003 production decline", description: "", recommended_action: null, notes: null,
      well_id: 3, well_code: "NDF-01-003", field_id: 1, field_name: "Niger Delta Field", facility_id: 1, facility_name: null,
      equipment_id: null, equipment_tag: null, maintenance_record_id: null, maintenance_work_order_number: null,
      production_loss_id: null, threshold_value: null, current_value: null, unit: null, dedup_key: "k1", occurrence_count: 1,
      triggered_at: "2026-08-14T00:00:00Z", last_detected_at: "2026-08-14T00:00:00Z", acknowledged_at: null, resolved_at: null,
      acknowledged_by_name: null, resolved_by_name: null, created_at: "2026-08-14T00:00:00Z", updated_at: "2026-08-14T00:00:00Z",
      disclaimer_text: "",
    },
  ],
  disclaimer_text: "Rule-based decision-support indicator requiring review.",
};

const costRevenue: api.CostRevenueDashboard = {
  period_start: "2026-08-01T00:00:00Z",
  period_end: "2026-08-14T23:59:59Z",
  production: { oil_bbl: 12500, gas_mscf: 8400, boe: 13900 },
  revenue: { oil: [], gas: [], total: [{ currency: "USD", amount: 900000 }] },
  costs: { operating: [], maintenance: [], energy: [], other: [], total: [{ currency: "USD", amount: 400000 }] },
  economics: {
    margin: [{ currency: "USD", amount: 500000 }],
    cost_per_bbl: [{ currency: "USD", amount: 32 }],
    cost_per_boe: [],
    revenue_per_bbl: [],
    revenue_per_boe: [],
    currency_mismatch: false,
  },
  production_loss: { estimated_lost_oil_bbl: 220, estimated_lost_gas_mscf: 90, estimated_lost_revenue: [], downtime_hours: 18 },
  disclaimer_text: "Management/analytical estimate, not an audited accounting figure.",
};

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "getProductionKpis").mockResolvedValue(productionKpis);
    vi.spyOn(api, "getAlertSummary").mockResolvedValue(alertSummary);
    vi.spyOn(api, "getCostRevenueDashboard").mockResolvedValue(costRevenue);
    vi.spyOn(api, "getProductionTrends").mockResolvedValue({ metric: "oil_gas_water", points: [] });
    vi.spyOn(api, "getEquipmentDashboard").mockResolvedValue({
      status_counts: { total: 5, operating: 4, standby: 1, maintenance: 0, failed: 0, decommissioned: 0, unknown: 0, attention_count: 0 },
      health_distribution: { buckets: [{ band: "Good", count: 4 }, { band: "Critical", count: 1 }], unscored_count: 0 },
    });
    vi.spyOn(api, "getProductionLossDashboard").mockResolvedValue({
      event_count: 3, total_oil_bopd_lost: 100, total_gas_mscfd_lost: 50, total_revenue_impact: 5000, avg_downtime_hours: 6,
      by_category: [{ category: "equipment_failure", count: 2 }],
      disclaimer_text: "Decision-support estimate, not a certified financial figure.",
    });
    vi.spyOn(api, "getMaintenanceDashboard").mockResolvedValue({
      status_counts: { total: 3, scheduled: 1, open: 1, in_progress: 0, waiting_for_parts: 0, completed: 1, cancelled: 0, overdue: 1, emergency_count: 0, computed_overdue_count: 1 },
      total_cost: 8000,
      total_downtime_hours: 12,
      equipment_requiring_maintenance: [
        { equipment_id: 1, equipment_tag: "COMP-01", equipment_name: "Compressor 1", next_maintenance_due: "2026-08-10", days_from_today: -4 },
      ],
    });
    vi.spyOn(api, "getInsightSummary").mockResolvedValue({
      total: 6, open_count: 2,
      by_severity: { critical: 1, high: 1, medium: 0, low: 0, informational: 0 },
      by_category: [], by_confidence: {},
      recent: [],
      critical: [
        {
          id: 1, insight_type: "production_decline", category: "production", severity: "critical", status: "new",
          generated_by: "rule_engine", ai_provider: null, ai_model: null, ai_interpretation: null,
          title: "Sustained production decline on NDF-01-003", summary: "", recommended_investigation: null,
          data_quality_note: null, confidence_level: "high",
          estimated_production_impact_value: null, estimated_production_impact_unit: null, estimated_production_impact_note: null,
          estimated_financial_impact_value: null, estimated_financial_impact_currency: null, estimated_financial_impact_note: null,
          well_id: 3, well_code: "NDF-01-003", field_id: 1, field_name: "Niger Delta Field", facility_id: null, facility_name: null,
          equipment_id: null, equipment_tag: null, maintenance_record_id: null, maintenance_work_order_number: null,
          production_loss_id: null, alert_id: null, dedup_key: "d1", occurrence_count: 1,
          generated_at: "2026-08-14T00:00:00Z", last_confirmed_at: "2026-08-14T00:00:00Z", is_stale: false, days_since_confirmed: 0,
          created_at: "2026-08-14T00:00:00Z", updated_at: "2026-08-14T00:00:00Z",
          disclaimer_text: "", evidence: [], feedback: [],
        },
      ],
      disclaimer_text: "",
    });
  });

  it("renders the hero production KPIs", async () => {
    render(<DashboardPage />);
    await waitFor(() => expect(screen.getByText("12,500")).toBeInTheDocument());
    expect(screen.getByText("8,400")).toBeInTheDocument();
    expect(screen.getByText("18")).toBeInTheDocument();
  });

  it("replaces the previously-fake KPIs with real Cost & Revenue figures", async () => {
    render(<DashboardPage />);
    expect(await screen.findByText("220")).toBeInTheDocument();
    expect(screen.getByText("$32.00")).toBeInTheDocument();
    expect(screen.getByText("$500,000.00")).toBeInTheDocument();
  });

  it("renders the production trend chart and the two chart-row widgets", async () => {
    render(<DashboardPage />);
    expect(await screen.findByText("Production Trend")).toBeInTheDocument();
    expect(screen.getByText("Equipment Health Distribution")).toBeInTheDocument();
    expect(screen.getByText("Production Loss by Category")).toBeInTheDocument();
  });

  it("renders the needs-attention list widgets with real data and view-all links", async () => {
    render(<DashboardPage />);

    expect(await screen.findByText("Well NDF-01-003 production decline")).toBeInTheDocument();
    expect(screen.getByText("Sustained production decline on NDF-01-003")).toBeInTheDocument();
    expect(screen.getByText("Compressor 1")).toBeInTheDocument();
    expect(screen.getByText("4d overdue")).toBeInTheDocument();

    const viewAllLinks = screen.getAllByText("View all →");
    expect(viewAllLinks).toHaveLength(3);
    expect(viewAllLinks[0].closest("a")).toHaveAttribute("href", "/alerts");
    expect(viewAllLinks[1].closest("a")).toHaveAttribute("href", "/ai-insights");
    expect(viewAllLinks[2].closest("a")).toHaveAttribute("href", "/maintenance");
  });

  it("renders a disclaimer footer", async () => {
    render(<DashboardPage />);
    expect(await screen.findByText("Management/analytical estimate, not an audited accounting figure.")).toBeInTheDocument();
  });
});
