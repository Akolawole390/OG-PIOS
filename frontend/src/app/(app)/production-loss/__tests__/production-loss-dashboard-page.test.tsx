import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ProductionLossDashboardPage from "@/app/(app)/production-loss/page";
import * as api from "@/lib/api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/production-loss",
}));

describe("ProductionLossDashboardPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "getProductionLossDashboard").mockResolvedValue({
      event_count: 5,
      total_oil_bopd_lost: 500,
      total_gas_mscfd_lost: 250,
      total_revenue_impact: 35750,
      avg_downtime_hours: 6.5,
      by_category: [{ category: "equipment_failure", count: 3 }],
      disclaimer_text: "Rule-based estimate — not a certified financial figure.",
    });
    vi.spyOn(api, "getProductionLossByScope").mockResolvedValue({ group_by: "category", bars: [] });
    vi.spyOn(api, "getProductionLossTrend").mockResolvedValue({ points: [] });
  });

  it("renders dashboard KPIs and the disclaimer", async () => {
    render(<ProductionLossDashboardPage />);

    await waitFor(() => expect(screen.getByText("Production Loss Dashboard")).toBeInTheDocument());
    expect(await screen.findByText("5")).toBeInTheDocument();
    expect(screen.getByText("Rule-based estimate — not a certified financial figure.")).toBeInTheDocument();
  });
});
