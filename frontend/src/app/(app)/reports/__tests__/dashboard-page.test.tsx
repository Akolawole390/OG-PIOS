import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ReportsPage from "@/app/(app)/reports/page";
import * as api from "@/lib/api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/reports",
}));

const reportTypes: api.ReportTypeInfo[] = [
  { id: "daily_operations", label: "Daily Operations Report", sections: ["production", "alerts"] },
  { id: "weekly_production", label: "Weekly Production Report", sections: ["production_trend"] },
  { id: "monthly_management", label: "Monthly Management Report", sections: ["executive_summary", "production"] },
  { id: "what_if_scenario", label: "What-If Scenario Report", sections: ["scenario"] },
];

const listItem: api.ReportListItem = {
  id: 1,
  report_type: "daily_operations",
  name: "Daily Ops - Niger Delta",
  description: null,
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
};

describe("ReportsPage (dashboard)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "getReportTypes").mockResolvedValue({ types: reportTypes });
  });

  it("renders quick-generate cards for all 4 report types", async () => {
    vi.spyOn(api, "listReports").mockResolvedValue({ items: [], total: 0, page: 1, page_size: 8 });

    render(<ReportsPage />);

    expect(await screen.findByText("Generate Daily Operations Report")).toBeInTheDocument();
    expect(screen.getByText("Generate Weekly Production Report")).toBeInTheDocument();
    expect(screen.getByText("Generate Monthly Management Report")).toBeInTheDocument();
    expect(screen.getByText("Generate What-If Scenario Report")).toBeInTheDocument();
  });

  it("shows an empty state when there are no recent reports", async () => {
    vi.spyOn(api, "listReports").mockResolvedValue({ items: [], total: 0, page: 1, page_size: 8 });

    render(<ReportsPage />);

    await waitFor(() => expect(screen.getByText("No reports generated yet.")).toBeInTheDocument());
  });

  it("renders recently generated reports", async () => {
    vi.spyOn(api, "listReports").mockResolvedValue({ items: [listItem], total: 1, page: 1, page_size: 8 });

    render(<ReportsPage />);

    expect(await screen.findByText("Daily Ops - Niger Delta")).toBeInTheDocument();
  });

  it("notes that scheduled reports are not yet implemented", async () => {
    vi.spyOn(api, "listReports").mockResolvedValue({ items: [], total: 0, page: 1, page_size: 8 });

    render(<ReportsPage />);

    expect(await screen.findByText(/not yet implemented/)).toBeInTheDocument();
  });
});
