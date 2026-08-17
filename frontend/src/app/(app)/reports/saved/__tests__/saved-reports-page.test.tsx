import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import SavedReportsPage from "@/app/(app)/reports/saved/page";
import * as api from "@/lib/api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/reports/saved",
}));

const items: api.ReportListItem[] = [
  {
    id: 1,
    report_type: "monthly_management",
    name: "August Management Report",
    description: "Monthly summary",
    created_by_id: 1,
    created_by_name: "Admin",
    period_start: "2026-08-01T00:00:00Z",
    period_end: "2026-08-31T23:59:59Z",
    calculation_version: "1.0",
    status: "generated",
    last_generated_at: "2026-08-01T12:00:00Z",
    created_at: "2026-08-01T12:00:00Z",
    updated_at: "2026-08-01T12:00:00Z",
    has_results: true,
  },
];

describe("SavedReportsPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders saved reports with their type and creator", async () => {
    vi.spyOn(api, "listReports").mockResolvedValue({ items, total: 1, page: 1, page_size: 25 });

    render(<SavedReportsPage />);

    expect(await screen.findByText("August Management Report")).toBeInTheDocument();
    expect(screen.getAllByText("Monthly Management").length).toBeGreaterThan(0);
    expect(screen.getByText("Admin")).toBeInTheDocument();
  });

  it("shows an empty state when there are no saved reports", async () => {
    vi.spyOn(api, "listReports").mockResolvedValue({ items: [], total: 0, page: 1, page_size: 25 });

    render(<SavedReportsPage />);

    await waitFor(() => expect(screen.getByText("No saved reports yet.")).toBeInTheDocument());
  });
});
