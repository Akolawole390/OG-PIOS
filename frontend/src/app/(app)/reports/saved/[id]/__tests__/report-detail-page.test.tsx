import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ReportDetailPage from "@/app/(app)/reports/saved/[id]/page";
import * as api from "@/lib/api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/reports/saved/1",
  useParams: () => ({ id: "1" }),
  useRouter: () => ({ push: vi.fn() }),
}));

const results: api.ReportResults = {
  report_type: "daily_operations",
  generated_at: "2026-08-01T12:00:00Z",
  filters: { date_from: "2026-08-01", date_to: "2026-08-01", field_id: 1 },
  sections: {
    production: {
      kpis: {
        total_oil_bbl: 5000,
        total_gas_mscf: 2500,
        total_water_bbl: 1000,
        avg_daily_oil_bopd: 5000,
        avg_daily_gas_mscfd: 2500,
        avg_daily_water_bwpd: 1000,
        avg_water_cut_pct: 20,
        avg_gor: 500,
        boe: 5416,
        boe_gas_factor: 6000,
        producing_wells_count: 5,
        target_oil_bopd: 6000,
        target_variance_pct: -16.7,
        reference_date: "2026-08-01",
        days_in_range: 1,
      },
      _traceability: { source_module: "production.get_production_kpis", methodology: "test", record_count: null },
    },
  },
  disclaimer_text: "Planning estimate - not a guaranteed outcome.",
  synthetic_data_disclaimer: "Development environment: synthetic data.",
};

const report: api.Report = {
  id: 1,
  report_type: "daily_operations",
  name: "Daily Ops - test",
  description: "test report",
  created_by_id: 1,
  created_by_name: "Admin",
  period_start: "2026-08-01T00:00:00Z",
  period_end: "2026-08-01T23:59:59Z",
  calculation_version: "1.0",
  status: "generated",
  last_generated_at: "2026-08-01T12:00:00Z",
  created_at: "2026-08-01T12:00:00Z",
  updated_at: "2026-08-01T12:00:00Z",
  has_results: true,
  filters: { date_from: "2026-08-01", date_to: "2026-08-01", field_id: 1 },
  sections: ["production"],
  results,
  disclaimer_text: "Planning estimate - not a guaranteed outcome.",
};

describe("ReportDetailPage", () => {
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
    vi.spyOn(api, "getReport").mockResolvedValue(report);
  });

  it("renders the report's sections and disclaimers", async () => {
    render(<ReportDetailPage />);

    await waitFor(() => expect(screen.getAllByText("Daily Ops - test").length).toBeGreaterThan(0));
    expect(screen.getByText("Production")).toBeInTheDocument();
    expect(screen.getByText("Planning estimate - not a guaranteed outcome.")).toBeInTheDocument();
    expect(screen.getByText("Development environment: synthetic data.")).toBeInTheDocument();
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

    render(<ReportDetailPage />);

    await waitFor(() => expect(screen.getAllByText("Daily Ops - test").length).toBeGreaterThan(0));
    expect(screen.queryByText("Regenerate Against Current Data")).not.toBeInTheDocument();
    expect(screen.getByText("Export CSV")).toBeInTheDocument();
  });

  it("regenerates the report", async () => {
    const regenerateSpy = vi.spyOn(api, "regenerateReport").mockResolvedValue(report);

    render(<ReportDetailPage />);
    await waitFor(() => expect(screen.getAllByText("Daily Ops - test").length).toBeGreaterThan(0));

    fireEvent.click(screen.getByText("Regenerate Against Current Data"));

    await waitFor(() => expect(regenerateSpy).toHaveBeenCalledWith(1));
  });

  it("exports the report as CSV", async () => {
    const exportSpy = vi.spyOn(api, "exportReport").mockResolvedValue(undefined);

    render(<ReportDetailPage />);
    await waitFor(() => expect(screen.getAllByText("Daily Ops - test").length).toBeGreaterThan(0));

    fireEvent.click(screen.getByText("Export CSV"));

    await waitFor(() => expect(exportSpy).toHaveBeenCalledWith(1, "csv", "Daily Ops - test.csv"));
  });
});
