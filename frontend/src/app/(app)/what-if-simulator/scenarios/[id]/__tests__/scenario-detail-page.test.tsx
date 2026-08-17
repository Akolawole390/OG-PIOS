import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ScenarioDetailPage from "@/app/(app)/what-if-simulator/scenarios/[id]/page";
import * as api from "@/lib/api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/what-if-simulator/scenarios/1",
  useParams: () => ({ id: "1" }),
  useRouter: () => ({ push: vi.fn() }),
}));

const results: api.ScenarioResults = {
  baseline: {
    period_start: "2026-07-01",
    period_end: "2026-07-31",
    period_days: 31,
    oil_bbl: 10000,
    gas_mscf: 5000,
    boe: 10833,
    oil_price: 70,
    oil_price_currency: "USD",
    gas_price: 3,
    gas_price_currency: "USD",
    revenue: [{ currency: "USD", amount: 715000 }],
    operating_cost: [{ currency: "USD", amount: 100000 }],
    maintenance_cost: [{ currency: "USD", amount: 20000 }],
    total_cost: [{ currency: "USD", amount: 120000 }],
    lost_oil_bbl: 50,
    lost_gas_mscf: 20,
    production_loss_revenue: [{ currency: "USD", amount: 3500 }],
    downtime_hours: 100,
    margin: [{ currency: "USD", amount: 595000 }],
    margin_currency_mismatch: false,
    data_sufficient: true,
    missing_data_note: null,
  },
  scenario: {
    oil_bbl: 10000,
    gas_mscf: 5000,
    boe: 10833,
    oil_price: 70,
    oil_price_currency: "USD",
    gas_price: 3,
    gas_price_currency: "USD",
    revenue: [{ currency: "USD", amount: 715000 }],
    operating_cost: [{ currency: "USD", amount: 100000 }],
    maintenance_cost: [{ currency: "USD", amount: 20000 }],
    total_cost: [{ currency: "USD", amount: 120000 }],
    lost_oil_bbl: 50,
    lost_gas_mscf: 20,
    production_loss_revenue: [{ currency: "USD", amount: 3500 }],
    downtime_hours: 80,
    margin: [{ currency: "USD", amount: 615000 }],
    margin_currency_mismatch: false,
    recovered_downtime_hours: 20,
    recovered_production_bbl: 83.3,
    potential_loss_reduction_oil_bbl: 0,
    potential_loss_reduction_gas_mscf: 0,
    potential_loss_reduction_revenue: [],
    potential_cost_saving: [],
  },
  comparison: [
    {
      metric: "Oil Production (bbl)",
      baseline: 10000,
      scenario: 10000,
      difference: 0,
      pct_change: 0,
      currency: null,
      direction: "neutral",
    },
  ],
  guardrail_flags: [],
};

const scenario: api.Scenario = {
  id: 1,
  name: "Downtime reduction 20%",
  description: "Test scenario",
  created_by_id: 1,
  created_by_name: "Admin",
  baseline_date_from: "2026-07-01",
  baseline_date_to: "2026-07-31",
  field_id: 1,
  field_name: "Niger Delta Field",
  facility_id: null,
  facility_name: null,
  well_id: null,
  well_code: null,
  equipment_id: null,
  equipment_tag: null,
  calculation_version: "1.0",
  last_run_at: "2026-08-01T12:00:00Z",
  created_at: "2026-08-01T12:00:00Z",
  updated_at: "2026-08-01T12:00:00Z",
  has_results: true,
  assumptions: { downtime_change_pct: -20 },
  results,
  disclaimer_text: "Planning estimate — not a guaranteed outcome.",
};

describe("ScenarioDetailPage", () => {
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
    vi.spyOn(api, "getScenario").mockResolvedValue(scenario);
  });

  it("renders the scenario's KPIs and comparison table", async () => {
    render(<ScenarioDetailPage />);

    await waitFor(() => expect(screen.getAllByText("Downtime reduction 20%").length).toBeGreaterThan(0));
    expect(screen.getByText("Baseline vs. Scenario")).toBeInTheDocument();
    expect(screen.getAllByText("Oil Production (bbl)").length).toBeGreaterThan(0);
    expect(screen.getByText("Planning estimate — not a guaranteed outcome.")).toBeInTheDocument();
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

    render(<ScenarioDetailPage />);

    await waitFor(() => expect(screen.getAllByText("Downtime reduction 20%").length).toBeGreaterThan(0));
    expect(screen.queryByText("Rerun Against Current Data")).not.toBeInTheDocument();
  });

  it("reruns the scenario against current data", async () => {
    const rerunSpy = vi.spyOn(api, "rerunScenario").mockResolvedValue(scenario);

    render(<ScenarioDetailPage />);
    await waitFor(() => expect(screen.getAllByText("Downtime reduction 20%").length).toBeGreaterThan(0));

    fireEvent.click(screen.getByText("Rerun Against Current Data"));

    await waitFor(() => expect(rerunSpy).toHaveBeenCalledWith(1));
  });

  it("requests and displays an AI interpretation", async () => {
    const interpretSpy = vi.spyOn(api, "interpretScenario").mockResolvedValue({
      scenario_id: 1,
      interpretation: "Fake AI interpretation.",
      provider: "fake",
      model: "fake-model",
      disclaimer_text: "Planning estimate — not a guaranteed outcome.",
    });

    render(<ScenarioDetailPage />);
    await waitFor(() => expect(screen.getAllByText("Downtime reduction 20%").length).toBeGreaterThan(0));

    fireEvent.click(screen.getByText("Add AI Interpretation"));

    await waitFor(() => expect(interpretSpy).toHaveBeenCalledWith(1));
    expect(await screen.findByText("Fake AI interpretation.")).toBeInTheDocument();
  });
});
