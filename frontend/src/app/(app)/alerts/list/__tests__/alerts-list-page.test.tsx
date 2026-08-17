import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AlertsListPage from "@/app/(app)/alerts/list/page";
import * as api from "@/lib/api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/alerts/list",
}));

const mockAlert: api.AlertEntry = {
  id: 1,
  alert_type: "maintenance_overdue",
  category: "maintenance",
  source_module: "maintenance",
  severity: "high",
  status: "new",
  title: "WO-000009 — Maintenance Overdue",
  description: "Work order WO-000009 for ESP-01 was due 2026-07-20 and is 10 day(s) overdue.",
  recommended_action: "Reschedule or complete this work order as soon as possible.",
  notes: null,
  well_id: 1,
  well_code: "PL-01",
  field_id: 1,
  field_name: "Field A",
  facility_id: 1,
  facility_name: "Facility A",
  equipment_id: 1,
  equipment_tag: "ESP-01",
  maintenance_record_id: 9,
  maintenance_work_order_number: "WO-000009",
  production_loss_id: null,
  threshold_value: null,
  current_value: 10,
  unit: "days overdue",
  dedup_key: "maintenance_overdue:work_order:9",
  occurrence_count: 1,
  triggered_at: "2026-07-30T00:00:00Z",
  last_detected_at: "2026-07-30T00:00:00Z",
  acknowledged_at: null,
  resolved_at: null,
  acknowledged_by_name: null,
  resolved_by_name: null,
  created_at: "2026-07-30T00:00:00Z",
  updated_at: "2026-07-30T00:00:00Z",
  disclaimer_text: "Rule-based alert — not a guaranteed conclusion or autonomous action.",
};

describe("AlertsListPage", () => {
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
    vi.spyOn(api, "listFacilities").mockResolvedValue([]);
    vi.spyOn(api, "listWells").mockResolvedValue({ items: [], total: 0, page: 1, page_size: 100 });
    vi.spyOn(api, "listEquipment").mockResolvedValue({ items: [], total: 0, page: 1, page_size: 200 });
  });

  it("renders alerts and shows Add Alert for an admin", async () => {
    vi.spyOn(api, "listAlerts").mockResolvedValue({ items: [mockAlert], total: 1, page: 1, page_size: 25 });

    render(<AlertsListPage />);

    await waitFor(() => expect(screen.getByText("WO-000009 — Maintenance Overdue")).toBeInTheDocument(), {
      timeout: 2000,
    });
    expect(screen.getByText("Add Alert")).toBeInTheDocument();
  });

  it("refetches with the search term after typing", async () => {
    const listAlertsSpy = vi
      .spyOn(api, "listAlerts")
      .mockResolvedValue({ items: [mockAlert], total: 1, page: 1, page_size: 25 });

    render(<AlertsListPage />);
    await waitFor(() => expect(listAlertsSpy).toHaveBeenCalled(), { timeout: 2000 });

    fireEvent.change(screen.getByPlaceholderText(/search title\/description/i), { target: { value: "overdue" } });

    await waitFor(
      () => expect(listAlertsSpy).toHaveBeenLastCalledWith(expect.objectContaining({ search: "overdue" })),
      { timeout: 2000 },
    );
  });

  it("hides Add Alert for a Viewer", async () => {
    vi.spyOn(api, "getCurrentUser").mockResolvedValue({
      id: 2,
      email: "viewer@ogpios.dev",
      full_name: "Viewer",
      is_active: true,
      role_id: 7,
      role_name: "Viewer",
    });
    vi.spyOn(api, "listAlerts").mockResolvedValue({ items: [], total: 0, page: 1, page_size: 25 });

    render(<AlertsListPage />);

    await waitFor(() => expect(screen.getByText("No alerts found.")).toBeInTheDocument(), { timeout: 2000 });
    expect(screen.queryByText("Add Alert")).not.toBeInTheDocument();
  });
});
