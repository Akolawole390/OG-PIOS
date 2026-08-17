import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ProductionLossListPage from "@/app/(app)/production-loss/list/page";
import * as api from "@/lib/api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/production-loss/list",
}));

const mockEntry: api.ProductionLossEntry = {
  id: 1,
  loss_date: "2026-01-15",
  category: "equipment_failure",
  cause: "ESP failure",
  downtime_hours: 6,
  well_id: 1,
  well_code: "PL-01",
  equipment_id: 1,
  equipment_tag: "ESP-01",
  equipment_name: "ESP Unit 1",
  field_id: 1,
  field_name: "Field A",
  facility_id: 1,
  facility_name: "Facility A",
  downtime_event_id: 5,
  maintenance_record_id: 9,
  work_order_number: "WO-000009",
  estimated_bopd_lost: 100,
  estimated_mscf_lost: 50,
  estimated_revenue_impact: 7150,
  currency: "USD",
  oil_price_per_bbl: 70,
  gas_price_per_mscf: 3,
  disclaimer_text: "Rule-based estimate — not a certified financial figure.",
  created_at: "2026-01-15T00:00:00Z",
  updated_at: "2026-01-15T00:00:00Z",
};

describe("ProductionLossListPage", () => {
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
    vi.spyOn(api, "listEquipment").mockResolvedValue({ items: [], total: 0, page: 1, page_size: 200 });
  });

  it("renders production loss records and shows Add Record for an admin", async () => {
    vi.spyOn(api, "listProductionLoss").mockResolvedValue({ items: [mockEntry], total: 1, page: 1, page_size: 25 });

    render(<ProductionLossListPage />);

    await waitFor(() => expect(screen.getByText("2026-01-15")).toBeInTheDocument(), { timeout: 2000 });
    expect(screen.getByText("PL-01 / ESP-01")).toBeInTheDocument();
    expect(screen.getByText("Add Record")).toBeInTheDocument();
  });

  it("refetches with the search term after typing", async () => {
    const listProductionLossSpy = vi
      .spyOn(api, "listProductionLoss")
      .mockResolvedValue({ items: [mockEntry], total: 1, page: 1, page_size: 25 });

    render(<ProductionLossListPage />);
    await waitFor(() => expect(listProductionLossSpy).toHaveBeenCalled(), { timeout: 2000 });

    fireEvent.change(screen.getByPlaceholderText(/search cause/i), { target: { value: "ESP" } });

    await waitFor(
      () => expect(listProductionLossSpy).toHaveBeenLastCalledWith(expect.objectContaining({ search: "ESP" })),
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
    vi.spyOn(api, "listProductionLoss").mockResolvedValue({ items: [], total: 0, page: 1, page_size: 25 });

    render(<ProductionLossListPage />);

    await waitFor(() => expect(screen.getByText("No production loss records found.")).toBeInTheDocument(), {
      timeout: 2000,
    });
    expect(screen.queryByText("Add Record")).not.toBeInTheDocument();
  });
});
