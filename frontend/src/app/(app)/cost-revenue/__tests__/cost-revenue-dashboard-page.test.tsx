import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CostRevenueDashboardPage from "@/app/(app)/cost-revenue/page";
import * as api from "@/lib/api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/cost-revenue",
}));

describe("CostRevenueDashboardPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "getCostAlerts").mockResolvedValue({ alerts: [], disclaimer_text: "Rule-based, not AI-driven." });
  });

  it("renders a currency-mismatch warning and never shows a fabricated blended margin", async () => {
    vi.spyOn(api, "getCostRevenueDashboard").mockResolvedValue({
      period_start: "2026-01-01",
      period_end: "2026-01-31",
      production: { oil_bbl: 1000, gas_mscf: 500, boe: 1083 },
      revenue: {
        oil: [{ currency: "USD", amount: 35000 }],
        gas: [],
        total: [{ currency: "USD", amount: 35000 }],
      },
      costs: {
        operating: [{ currency: "NGN", amount: 5000000 }],
        maintenance: [],
        energy: [],
        other: [{ currency: "NGN", amount: 5000000 }],
        total: [{ currency: "NGN", amount: 5000000 }],
      },
      economics: {
        margin: [],
        cost_per_bbl: [],
        cost_per_boe: [],
        revenue_per_bbl: [{ currency: "USD", amount: 35 }],
        revenue_per_boe: [],
        currency_mismatch: true,
      },
      production_loss: {
        estimated_lost_oil_bbl: 0,
        estimated_lost_gas_mscf: 0,
        estimated_lost_revenue: [],
        downtime_hours: 0,
      },
      disclaimer_text: "Estimates for management/analyst review — not audited accounting figures.",
    });

    render(<CostRevenueDashboardPage />);

    await waitFor(() => expect(screen.getByText("Cost & Revenue Dashboard")).toBeInTheDocument());
    expect(
      await screen.findByText(/margin cannot be computed without inventing an exchange rate/i),
    ).toBeInTheDocument();
    expect(screen.getByText("Estimates for management/analyst review — not audited accounting figures.")).toBeInTheDocument();
  });
});
