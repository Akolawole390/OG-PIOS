import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import MaintenanceListPage from "@/app/(app)/maintenance/list/page";
import * as api from "@/lib/api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/maintenance/list",
}));

const mockEntry: api.MaintenanceEntry = {
  id: 1,
  work_order_number: "WO-000001",
  equipment_id: 1,
  equipment_tag: "COMP-01",
  equipment_name: "Compressor 1",
  equipment_type: "compressor",
  field_id: 1,
  field_name: "Field A",
  facility_id: 1,
  facility_name: "Facility A",
  well_id: null,
  well_code: null,
  maintenance_type: "preventive",
  priority: "medium",
  status: "scheduled",
  description: null,
  planned_start_date: "2026-02-01",
  planned_completion_date: "2026-02-03",
  start_date: null,
  completion_date: null,
  technician_id: null,
  technician_name: null,
  labor_cost: null,
  parts_cost: null,
  contractor_cost: null,
  other_cost: null,
  cost: null,
  downtime_hours: null,
  failure_cause: null,
  corrective_action: null,
  notes: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("MaintenanceListPage", () => {
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
    vi.spyOn(api, "listEquipment").mockResolvedValue({ items: [], total: 0, page: 1, page_size: 200 });
    vi.spyOn(api, "listWells").mockResolvedValue({ items: [], total: 0, page: 1, page_size: 100 });
    vi.spyOn(api, "listFacilities").mockResolvedValue([]);
  });

  it("renders maintenance records and shows Create Work Order for an admin", async () => {
    vi.spyOn(api, "listMaintenance").mockResolvedValue({ items: [mockEntry], total: 1, page: 1, page_size: 25 });

    render(<MaintenanceListPage />);

    await waitFor(() => expect(screen.getByText("WO-000001")).toBeInTheDocument(), { timeout: 2000 });
    expect(screen.getByText("COMP-01")).toBeInTheDocument();
    expect(screen.getByText("Create Work Order")).toBeInTheDocument();
  });

  it("refetches with the search term after typing", async () => {
    const listMaintenanceSpy = vi
      .spyOn(api, "listMaintenance")
      .mockResolvedValue({ items: [mockEntry], total: 1, page: 1, page_size: 25 });

    render(<MaintenanceListPage />);
    await waitFor(() => expect(listMaintenanceSpy).toHaveBeenCalled(), { timeout: 2000 });

    fireEvent.change(screen.getByPlaceholderText(/search description or work order/i), {
      target: { value: "pump" },
    });

    await waitFor(
      () => expect(listMaintenanceSpy).toHaveBeenLastCalledWith(expect.objectContaining({ search: "pump" })),
      { timeout: 2000 },
    );
  });

  it("hides Create Work Order for a Viewer", async () => {
    vi.spyOn(api, "getCurrentUser").mockResolvedValue({
      id: 2,
      email: "viewer@ogpios.dev",
      full_name: "Viewer",
      is_active: true,
      role_id: 7,
      role_name: "Viewer",
    });
    vi.spyOn(api, "listMaintenance").mockResolvedValue({ items: [], total: 0, page: 1, page_size: 25 });

    render(<MaintenanceListPage />);

    await waitFor(() => expect(screen.getByText("No maintenance records found.")).toBeInTheDocument(), {
      timeout: 2000,
    });
    expect(screen.queryByText("Create Work Order")).not.toBeInTheDocument();
  });
});
