import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CompareScenariosPage from "@/app/(app)/what-if-simulator/compare/page";
import * as api from "@/lib/api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/what-if-simulator/compare",
  useSearchParams: () => ({ get: () => null }),
}));

function makeResults(oilBbl: number, revenue: number, margin: number): api.ScenarioResults {
  return {
    baseline: {
      period_start: "2026-07-01",
      period_end: "2026-07-31",
      period_days: 31,
      oil_bbl: oilBbl,
      gas_mscf: 5000,
      boe: oilBbl,
      oil_price: 70,
      oil_price_currency: "USD",
      gas_price: 3,
      gas_price_currency: "USD",
      revenue: [{ currency: "USD", amount: revenue }],
      operating_cost: [{ currency: "USD", amount: 100000 }],
      maintenance_cost: [{ currency: "USD", amount: 20000 }],
      total_cost: [{ currency: "USD", amount: 120000 }],
      lost_oil_bbl: 50,
      lost_gas_mscf: 20,
      production_loss_revenue: [{ currency: "USD", amount: 3500 }],
      downtime_hours: 100,
      margin: [{ currency: "USD", amount: margin }],
      margin_currency_mismatch: false,
      data_sufficient: true,
      missing_data_note: null,
    },
    scenario: {
      oil_bbl: oilBbl,
      gas_mscf: 5000,
      boe: oilBbl,
      oil_price: 70,
      oil_price_currency: "USD",
      gas_price: 3,
      gas_price_currency: "USD",
      revenue: [{ currency: "USD", amount: revenue }],
      operating_cost: [{ currency: "USD", amount: 100000 }],
      maintenance_cost: [{ currency: "USD", amount: 20000 }],
      total_cost: [{ currency: "USD", amount: 120000 }],
      lost_oil_bbl: 50,
      lost_gas_mscf: 20,
      production_loss_revenue: [{ currency: "USD", amount: 3500 }],
      downtime_hours: 80,
      margin: [{ currency: "USD", amount: margin }],
      margin_currency_mismatch: false,
      recovered_downtime_hours: 20,
      recovered_production_bbl: 83.3,
      potential_loss_reduction_oil_bbl: 0,
      potential_loss_reduction_gas_mscf: 0,
      potential_loss_reduction_revenue: [],
      potential_cost_saving: [],
    },
    comparison: [],
    guardrail_flags: [],
  };
}

const items: api.ScenarioListItem[] = [
  {
    id: 1,
    name: "Downtime -10%",
    description: null,
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
  },
  {
    id: 2,
    name: "Downtime -30%",
    description: null,
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
  },
];

describe("CompareScenariosPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "listScenarios").mockResolvedValue({ items, total: 2, page: 1, page_size: 100 });
  });

  it("renders per-metric bar charts once 2+ scenarios are compared", async () => {
    vi.spyOn(api, "compareScenarios").mockResolvedValue({
      scenarios: [
        { id: 1, name: "Downtime -10%", results: makeResults(10000, 700000, 580000) },
        { id: 2, name: "Downtime -30%", results: makeResults(10500, 735000, 610000) },
      ],
      ai_narrative: null,
      disclaimer_text: "Planning estimate — not a guaranteed outcome.",
    });

    render(<CompareScenariosPage />);

    await screen.findByText("Downtime -10%");
    fireEvent.click(screen.getByLabelText(/Downtime -10%/));
    fireEvent.click(screen.getByLabelText(/Downtime -30%/));
    fireEvent.click(screen.getByText(/Compare 2 Selected/));

    await waitFor(() => expect(screen.getByText("Scenario Oil Production (bbl)")).toBeInTheDocument());
    expect(screen.getByText("Scenario Revenue (USD)")).toBeInTheDocument();
    expect(screen.getByText("Scenario Margin (USD)")).toBeInTheDocument();
  });

  it("does not render bar charts when no scenario has results yet", async () => {
    vi.spyOn(api, "compareScenarios").mockResolvedValue({
      scenarios: [
        { id: 1, name: "Downtime -10%", results: null },
        { id: 2, name: "Downtime -30%", results: null },
      ],
      ai_narrative: null,
      disclaimer_text: "Planning estimate — not a guaranteed outcome.",
    });

    render(<CompareScenariosPage />);

    await screen.findByText("Downtime -10%");
    fireEvent.click(screen.getByLabelText(/Downtime -10%/));
    fireEvent.click(screen.getByLabelText(/Downtime -30%/));
    fireEvent.click(screen.getByText(/Compare 2 Selected/));

    await waitFor(() => expect(screen.getAllByText("Not run yet.").length).toBe(2));
    expect(screen.queryByText("Scenario Oil Production (bbl)")).not.toBeInTheDocument();
  });
});
