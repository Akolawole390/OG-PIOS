import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import WhatIfSimulatorPage from "@/app/(app)/what-if-simulator/page";
import * as api from "@/lib/api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/what-if-simulator",
}));

const listItem: api.ScenarioListItem = {
  id: 1,
  name: "Downtime reduction 20%",
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
};

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
  comparison: [],
  guardrail_flags: [],
};

const scenario: api.Scenario = {
  ...listItem,
  assumptions: { downtime_change_pct: -20 },
  results,
  disclaimer_text: "Planning estimate — not a guaranteed outcome.",
};

describe("WhatIfSimulatorPage (dashboard)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("shows an empty state with a call to action when there are no scenarios", async () => {
    vi.spyOn(api, "listScenarios").mockResolvedValue({ items: [], total: 0, page: 1, page_size: 5 });

    render(<WhatIfSimulatorPage />);

    expect(await screen.findByText(/No scenarios yet/)).toBeInTheDocument();
    expect(screen.getByText("Build a Scenario")).toBeInTheDocument();
  });

  it("renders the most recently run scenario's KPIs and recent scenario list", async () => {
    vi.spyOn(api, "listScenarios").mockResolvedValue({ items: [listItem], total: 1, page: 1, page_size: 5 });
    vi.spyOn(api, "getScenario").mockResolvedValue(scenario);

    render(<WhatIfSimulatorPage />);

    await waitFor(() => expect(screen.getByText(/Most Recently Run/)).toBeInTheDocument());
    expect(screen.getAllByText("Downtime reduction 20%").length).toBeGreaterThan(0);
    expect(screen.getByText("Recent Scenarios")).toBeInTheDocument();
  });
});
