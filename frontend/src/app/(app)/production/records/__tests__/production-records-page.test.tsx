import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ProductionRecordsPage from "@/app/(app)/production/records/page";
import * as api from "@/lib/api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/production/records",
}));

const mockRecord: api.ProductionEntry = {
  id: 1,
  record_date: "2026-06-01",
  well_id: 1,
  well_code: "NDF-01-001",
  well_name: "NDF Well 001",
  facility_id: 1,
  facility_name: "Facility A",
  field_id: 1,
  field_name: "Field A",
  oil_bopd: 500,
  gas_mscfd: 300,
  water_bwpd: 50,
  water_cut_pct: 9.09,
  gor: 600,
  boe: 550,
  choke_size: 40,
  wellhead_pressure: 1500,
  tubing_pressure: 1700,
  casing_pressure: 900,
  flowline_pressure: 1200,
  wellhead_temperature: 180,
  downtime_hours: 0,
  warnings: null,
};

describe("ProductionRecordsPage", () => {
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
    vi.spyOn(api, "listWells").mockResolvedValue({ items: [], total: 0, page: 1, page_size: 100 });
    vi.spyOn(api, "listFacilities").mockResolvedValue([]);
  });

  it("renders production records and shows Add Record for an admin", async () => {
    vi.spyOn(api, "listProduction").mockResolvedValue({
      items: [mockRecord],
      total: 1,
      page: 1,
      page_size: 25,
    });

    render(<ProductionRecordsPage />);

    await waitFor(() => expect(screen.getByText("2026-06-01")).toBeInTheDocument(), { timeout: 2000 });
    expect(screen.getByText("NDF-01-001")).toBeInTheDocument();
    expect(screen.getByText("Add Record")).toBeInTheDocument();
  });

  it("refetches with the search term after typing", async () => {
    const listProductionSpy = vi.spyOn(api, "listProduction").mockResolvedValue({
      items: [mockRecord],
      total: 1,
      page: 1,
      page_size: 25,
    });

    render(<ProductionRecordsPage />);
    await waitFor(() => expect(listProductionSpy).toHaveBeenCalled(), { timeout: 2000 });

    fireEvent.change(screen.getByPlaceholderText(/search well id or name/i), {
      target: { value: "NDF" },
    });

    await waitFor(
      () => expect(listProductionSpy).toHaveBeenLastCalledWith(expect.objectContaining({ search: "NDF" })),
      { timeout: 2000 },
    );
  });

  it("hides Add Record for a Viewer", async () => {
    vi.spyOn(api, "getCurrentUser").mockResolvedValue({
      id: 2,
      email: "viewer@ogpios.dev",
      full_name: "Viewer",
      is_active: true,
      role_id: 7,
      role_name: "Viewer",
    });
    vi.spyOn(api, "listProduction").mockResolvedValue({ items: [], total: 0, page: 1, page_size: 25 });

    render(<ProductionRecordsPage />);

    await waitFor(() => expect(screen.getByText("No production records found.")).toBeInTheDocument(), {
      timeout: 2000,
    });
    expect(screen.queryByText("Add Record")).not.toBeInTheDocument();
    expect(screen.getByText("Export CSV")).toBeInTheDocument();
  });
});
