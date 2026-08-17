import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import WellsPage from "@/app/(app)/wells/page";
import * as api from "@/lib/api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/wells",
}));

const mockWell: api.Well = {
  id: 1,
  well_id: "NDF-01-001",
  name: "Test Well",
  well_type: "oil_producer",
  status: "active",
  artificial_lift_type: null,
  latitude: null,
  longitude: null,
  completion_date: null,
  completion_type: null,
  total_depth_ft: null,
  facility_id: 1,
  facility: { id: 1, name: "Facility A", facility_type: null, field: { id: 1, name: "Field A" } },
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("WellsPage", () => {
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
  });

  it("renders wells returned by the API and shows Add Well for an admin", async () => {
    vi.spyOn(api, "listWells").mockResolvedValue({
      items: [mockWell],
      total: 1,
      page: 1,
      page_size: 25,
    });

    render(<WellsPage />);

    await waitFor(() => expect(screen.getByText("NDF-01-001")).toBeInTheDocument(), { timeout: 2000 });
    expect(screen.getByText("Test Well")).toBeInTheDocument();
    expect(screen.getByText("Add Well")).toBeInTheDocument();
  });

  it("refetches with the search term after typing", async () => {
    const listWellsSpy = vi.spyOn(api, "listWells").mockResolvedValue({
      items: [mockWell],
      total: 1,
      page: 1,
      page_size: 25,
    });

    render(<WellsPage />);
    await waitFor(() => expect(listWellsSpy).toHaveBeenCalled(), { timeout: 2000 });

    fireEvent.change(screen.getByPlaceholderText(/search well id or name/i), {
      target: { value: "NDF" },
    });

    await waitFor(
      () => expect(listWellsSpy).toHaveBeenLastCalledWith(expect.objectContaining({ search: "NDF" })),
      { timeout: 2000 },
    );
  });

  it("hides Add Well for a Viewer", async () => {
    vi.spyOn(api, "getCurrentUser").mockResolvedValue({
      id: 2,
      email: "viewer@ogpios.dev",
      full_name: "Viewer",
      is_active: true,
      role_id: 7,
      role_name: "Viewer",
    });
    vi.spyOn(api, "listWells").mockResolvedValue({ items: [], total: 0, page: 1, page_size: 25 });

    render(<WellsPage />);

    await waitFor(() => expect(screen.getByText("No wells found.")).toBeInTheDocument(), { timeout: 2000 });
    expect(screen.queryByText("Add Well")).not.toBeInTheDocument();
  });
});
