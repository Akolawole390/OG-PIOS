import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Sidebar } from "@/components/navigation/Sidebar";
import { NAV_ITEMS } from "@/config/navigation";
import * as api from "@/lib/api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
}));

const mockWells: api.Well[] = [
  {
    id: 1,
    well_id: "NDF-01-001",
    name: "NDF Well 001",
    well_type: "oil_producer",
    status: "active",
    artificial_lift_type: null,
    latitude: null,
    longitude: null,
    completion_date: null,
    completion_type: null,
    total_depth_ft: null,
    facility_id: 1,
    facility: { id: 1, name: "NDF Flow Station A", facility_type: "platform", field: { id: 1, name: "Niger Delta Field" } },
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
  {
    id: 2,
    well_id: "NDF-01-002",
    name: "NDF Well 002",
    well_type: "gas_producer",
    status: "active",
    artificial_lift_type: null,
    latitude: null,
    longitude: null,
    completion_date: null,
    completion_type: null,
    total_depth_ft: null,
    facility_id: 1,
    facility: { id: 1, name: "NDF Flow Station A", facility_type: "platform", field: { id: 1, name: "Niger Delta Field" } },
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

describe("Sidebar", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
  });

  it("renders every navigation label", () => {
    render(<Sidebar />);

    for (const item of NAV_ITEMS) {
      expect(screen.getByText(item.label)).toBeInTheDocument();
    }
  });

  it("renders a pilot/synthetic-data badge", () => {
    render(<Sidebar />);

    expect(screen.getByText("PILOT · SYNTHETIC DATA")).toBeInTheDocument();
  });

  it("collapses to abbreviations and back on toggle", () => {
    render(<Sidebar />);

    expect(screen.getByText("Wells")).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("Collapse navigation"));
    expect(screen.queryByText("Wells")).not.toBeInTheDocument();
    expect(screen.getByText("WE")).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("Expand navigation"));
    expect(screen.getByText("Wells")).toBeInTheDocument();
    expect(screen.queryByText("WE")).not.toBeInTheDocument();
  });

  it("expands the Wells submenu and lists every well as a link", async () => {
    const listWellsSpy = vi.spyOn(api, "listWells").mockResolvedValue({
      items: mockWells,
      total: 2,
      page: 1,
      page_size: 100,
    });

    render(<Sidebar />);
    fireEvent.click(screen.getByLabelText("Expand wells list"));

    expect(listWellsSpy).toHaveBeenCalledWith({ page_size: 100, sort: "well_id" });

    const link1 = await screen.findByText("NDF-01-001");
    expect(link1.closest("a")).toHaveAttribute("href", "/wells/1");
    const link2 = screen.getByText("NDF-01-002");
    expect(link2.closest("a")).toHaveAttribute("href", "/wells/2");
  });

  it("does not refetch wells on a second expand", async () => {
    const listWellsSpy = vi.spyOn(api, "listWells").mockResolvedValue({
      items: mockWells,
      total: 2,
      page: 1,
      page_size: 100,
    });

    render(<Sidebar />);
    fireEvent.click(screen.getByLabelText("Expand wells list"));
    await screen.findByText("NDF-01-001");

    fireEvent.click(screen.getByLabelText("Collapse wells list"));
    fireEvent.click(screen.getByLabelText("Expand wells list"));

    await waitFor(() => expect(screen.getByText("NDF-01-001")).toBeInTheDocument());
    expect(listWellsSpy).toHaveBeenCalledTimes(1);
  });

  it("shows an inline error if the wells list fails to load", async () => {
    vi.spyOn(api, "listWells").mockRejectedValue(new Error("network error"));

    render(<Sidebar />);
    fireEvent.click(screen.getByLabelText("Expand wells list"));

    expect(await screen.findByText("Unable to load wells.")).toBeInTheDocument();
  });

  it("renders a Change Password link and a Log out button that calls logout()", () => {
    const logoutSpy = vi.spyOn(api, "logout").mockImplementation(() => undefined);

    render(<Sidebar />);

    const changePasswordLink = screen.getByText("Change Password");
    expect(changePasswordLink.closest("a")).toHaveAttribute("href", "/account/change-password");

    fireEvent.click(screen.getByText("Log out"));
    expect(logoutSpy).toHaveBeenCalledTimes(1);
  });
});
