import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import EquipmentListPage from "@/app/(app)/equipment/list/page";
import * as api from "@/lib/api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/equipment/list",
}));

const mockEquipment: api.Equipment = {
  id: 1,
  equipment_tag: "COMP-01",
  name: "Compressor 1",
  equipment_type: "compressor",
  manufacturer: null,
  model: null,
  serial_number: null,
  installation_date: null,
  commissioning_date: null,
  description: null,
  status: "operating",
  operating_hours: 1200,
  next_maintenance_due: null,
  facility_id: 1,
  well_id: null,
  field_id: 1,
  field_name: "Field A",
  facility_name: "Facility A",
  well_code: null,
  health_score: 92,
  health_band: "Excellent",
  last_maintenance_date: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("EquipmentListPage", () => {
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
  });

  it("renders equipment returned by the API and shows Add Equipment for an admin", async () => {
    vi.spyOn(api, "listEquipment").mockResolvedValue({
      items: [mockEquipment],
      total: 1,
      page: 1,
      page_size: 25,
    });

    render(<EquipmentListPage />);

    await waitFor(() => expect(screen.getByText("COMP-01")).toBeInTheDocument(), { timeout: 2000 });
    expect(screen.getByText("Compressor 1")).toBeInTheDocument();
    expect(screen.getByText("Add Equipment")).toBeInTheDocument();
  });

  it("refetches with the search term after typing", async () => {
    const listEquipmentSpy = vi.spyOn(api, "listEquipment").mockResolvedValue({
      items: [mockEquipment],
      total: 1,
      page: 1,
      page_size: 25,
    });

    render(<EquipmentListPage />);
    await waitFor(() => expect(listEquipmentSpy).toHaveBeenCalled(), { timeout: 2000 });

    fireEvent.change(screen.getByPlaceholderText(/search tag or name/i), {
      target: { value: "COMP" },
    });

    await waitFor(
      () => expect(listEquipmentSpy).toHaveBeenLastCalledWith(expect.objectContaining({ search: "COMP" })),
      { timeout: 2000 },
    );
  });

  it("hides Add Equipment for a Viewer", async () => {
    vi.spyOn(api, "getCurrentUser").mockResolvedValue({
      id: 2,
      email: "viewer@ogpios.dev",
      full_name: "Viewer",
      is_active: true,
      role_id: 7,
      role_name: "Viewer",
    });
    vi.spyOn(api, "listEquipment").mockResolvedValue({ items: [], total: 0, page: 1, page_size: 25 });

    render(<EquipmentListPage />);

    await waitFor(() => expect(screen.getByText("No equipment found.")).toBeInTheDocument(), { timeout: 2000 });
    expect(screen.queryByText("Add Equipment")).not.toBeInTheDocument();
  });
});
