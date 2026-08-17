import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import OperatingCostsPage from "@/app/(app)/cost-revenue/operating-costs/page";
import * as api from "@/lib/api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/cost-revenue/operating-costs",
}));

const mockEntry: api.OperatingCostEntry = {
  id: 1,
  cost_date: "2026-02-01",
  category: "Energy",
  amount: 1250.5,
  currency: "USD",
  description: "Generator fuel",
  cost_period: "monthly",
  source: "invoice",
  notes: "Synthetic/demo data — not a real operational cost record.",
  field_id: 1,
  field_name: "Field A",
  facility_id: 1,
  facility_name: "Facility A",
  well_id: null,
  well_code: null,
  equipment_id: null,
  equipment_tag: null,
  created_at: "2026-02-01T00:00:00Z",
  updated_at: "2026-02-01T00:00:00Z",
};

describe("OperatingCostsPage", () => {
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

  it("renders operating cost records and shows Add Cost for an admin", async () => {
    vi.spyOn(api, "listOperatingCosts").mockResolvedValue({ items: [mockEntry], total: 1, page: 1, page_size: 25 });

    render(<OperatingCostsPage />);

    await waitFor(() => expect(screen.getByText("2026-02-01")).toBeInTheDocument(), { timeout: 2000 });
    expect(screen.getByText("Field A / Facility A")).toBeInTheDocument();
    expect(screen.getByText("Add Cost")).toBeInTheDocument();
  });

  it("refetches with the search term after typing", async () => {
    const listOperatingCostsSpy = vi
      .spyOn(api, "listOperatingCosts")
      .mockResolvedValue({ items: [mockEntry], total: 1, page: 1, page_size: 25 });

    render(<OperatingCostsPage />);
    await waitFor(() => expect(listOperatingCostsSpy).toHaveBeenCalled(), { timeout: 2000 });

    fireEvent.change(screen.getByPlaceholderText(/search description/i), { target: { value: "fuel" } });

    await waitFor(
      () => expect(listOperatingCostsSpy).toHaveBeenLastCalledWith(expect.objectContaining({ search: "fuel" })),
      { timeout: 2000 },
    );
  });

  it("hides Add Cost for a Viewer", async () => {
    vi.spyOn(api, "getCurrentUser").mockResolvedValue({
      id: 2,
      email: "viewer@ogpios.dev",
      full_name: "Viewer",
      is_active: true,
      role_id: 7,
      role_name: "Viewer",
    });
    vi.spyOn(api, "listOperatingCosts").mockResolvedValue({ items: [], total: 0, page: 1, page_size: 25 });

    render(<OperatingCostsPage />);

    await waitFor(() => expect(screen.getByText("No operating cost records found.")).toBeInTheDocument(), {
      timeout: 2000,
    });
    expect(screen.queryByText("Add Cost")).not.toBeInTheDocument();
  });
});
