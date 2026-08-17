import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import MaintenanceDashboardPage from "@/app/(app)/maintenance/page";
import * as api from "@/lib/api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/maintenance",
}));

describe("MaintenanceDashboardPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "getMaintenanceDashboard").mockResolvedValue({
      status_counts: {
        total: 10,
        scheduled: 3,
        open: 2,
        in_progress: 1,
        waiting_for_parts: 1,
        completed: 2,
        cancelled: 1,
        overdue: 0,
        emergency_count: 1,
        computed_overdue_count: 2,
      },
      total_cost: 15000,
      total_downtime_hours: 42,
      equipment_requiring_maintenance: [
        { equipment_id: 1, equipment_tag: "COMP-01", equipment_name: "Compressor 1", next_maintenance_due: "2026-01-01", days_from_today: -5 },
      ],
    });
    vi.spyOn(api, "getMaintenanceByScope").mockResolvedValue({ group_by: "type", bars: [] });
    vi.spyOn(api, "getMaintenanceCostTrend").mockResolvedValue({ points: [] });
  });

  it("renders dashboard KPIs and the equipment-requiring-maintenance list", async () => {
    render(<MaintenanceDashboardPage />);

    await waitFor(() => expect(screen.getByText("Maintenance Dashboard")).toBeInTheDocument());
    expect(await screen.findByText("COMP-01 — Compressor 1")).toBeInTheDocument();
    expect(screen.getByText("5 day(s) overdue")).toBeInTheDocument();
  });
});
