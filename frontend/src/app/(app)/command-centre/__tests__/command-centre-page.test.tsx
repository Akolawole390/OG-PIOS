import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CommandCentrePage from "@/app/(app)/command-centre/page";
import * as api from "@/lib/api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/command-centre",
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

const equipmentDashboard: api.EquipmentDashboard = {
  status_counts: { total: 10, operating: 8, standby: 1, maintenance: 1, failed: 0, decommissioned: 0, unknown: 0, attention_count: 1 },
  health_distribution: { buckets: [{ band: "Good", count: 8 }, { band: "Monitor", count: 2 }], unscored_count: 0 },
};

const maintenanceDashboard: api.MaintenanceDashboard = {
  status_counts: { total: 4, scheduled: 1, open: 1, in_progress: 0, waiting_for_parts: 0, completed: 1, cancelled: 0, overdue: 1, emergency_count: 0, computed_overdue_count: 1 },
  total_cost: 8000,
  total_downtime_hours: 12,
  equipment_requiring_maintenance: [],
};

const alertSummary: api.AlertSummaryResponse = {
  total: 12,
  open_count: 4,
  by_severity: { critical: 1, high: 2, medium: 1, low: 0, informational: 0 },
  by_status: { new: 2, acknowledged: 2, investigating: 0, resolved: 6, dismissed: 2 },
  by_category: [],
  by_field: [],
  by_equipment: [],
  recent: [],
  disclaimer_text: "Rule-based decision-support indicator requiring review.",
};

const insightSummary: api.InsightSummary = {
  total: 6,
  open_count: 2,
  by_severity: { critical: 1, high: 1, medium: 0, low: 0, informational: 0 },
  by_category: [],
  by_confidence: {},
  recent: [],
  critical: [],
  disclaimer_text: "",
};

const productionIssues: api.ProductionIssuesResponse = {
  reference_date: "2026-08-14",
  down_wells: [
    { well_id: 3, well_code: "NDF-01-003", well_name: "Niger Delta 3", detail: "No production reported for 3 days" },
  ],
  zero_production_wells: [],
};

const equipmentIssues: api.EquipmentIssuesResponse = {
  items: [
    {
      id: 7,
      equipment_tag: "COMP-02",
      name: "Compressor 2",
      equipment_type: "compressor",
      status: "operating",
      health_score: 58,
      health_band: "Monitor",
      detail: "Vibration trending upward",
    },
  ],
};

describe("CommandCentrePage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "getProductionKpis").mockResolvedValue(productionKpis);
    vi.spyOn(api, "getEquipmentDashboard").mockResolvedValue(equipmentDashboard);
    vi.spyOn(api, "getMaintenanceDashboard").mockResolvedValue(maintenanceDashboard);
    vi.spyOn(api, "getAlertSummary").mockResolvedValue(alertSummary);
    vi.spyOn(api, "getInsightSummary").mockResolvedValue(insightSummary);
    vi.spyOn(api, "getProductionIssues").mockResolvedValue(productionIssues);
    vi.spyOn(api, "getEquipmentIssues").mockResolvedValue(equipmentIssues);
  });

  it("renders the page header and field status row", async () => {
    render(<CommandCentrePage />);
    expect(screen.getByText("AI Command Centre")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Field Status")).toBeInTheDocument());
    expect(screen.getAllByText("Production").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("HSE")).toBeInTheDocument();
    expect(screen.getAllByText("Not tracked").length).toBeGreaterThanOrEqual(2);
  });

  it("renders an estimated operations score derived from KPI data", async () => {
    render(<CommandCentrePage />);
    expect(await screen.findByText("Operations Score")).toBeInTheDocument();
    expect(screen.getByText("Estimated")).toBeInTheDocument();
  });

  it("renders wells and equipment requiring attention with links", async () => {
    render(<CommandCentrePage />);
    expect(await screen.findByText(/NDF-01-003/)).toBeInTheDocument();
    expect(screen.getByText(/COMP-02/)).toBeInTheDocument();
    expect(screen.getByText(/Compressor 2/)).toBeInTheDocument();
  });

  it("renders the Ask OG-PIOS panel with a link to the full assistant", async () => {
    render(<CommandCentrePage />);
    expect(screen.getByText("Ask OG-PIOS")).toBeInTheDocument();
    const link = screen.getByText("Open full assistant →");
    expect(link.closest("a")).toHaveAttribute("href", "/ai-insights/assistant");
  });
});
