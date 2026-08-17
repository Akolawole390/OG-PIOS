import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import SavedScenariosPage from "@/app/(app)/what-if-simulator/scenarios/page";
import * as api from "@/lib/api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/what-if-simulator/scenarios",
  useRouter: () => ({ push: vi.fn() }),
}));

const items: api.ScenarioListItem[] = [
  {
    id: 1,
    name: "Downtime reduction 20%",
    description: "Test scenario",
    created_by_id: 1,
    created_by_name: "Admin",
    baseline_date_from: "2026-07-01",
    baseline_date_to: "2026-07-31",
    field_id: 1,
    field_name: "Niger Delta Field",
    facility_id: null,
    facility_name: null,
    well_id: null,
    well_code: null,
    equipment_id: null,
    equipment_tag: null,
    calculation_version: "1.0",
    last_run_at: "2026-08-01T12:00:00Z",
    created_at: "2026-08-01T12:00:00Z",
    updated_at: "2026-08-01T12:00:00Z",
    has_results: true,
  },
];

describe("SavedScenariosPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders saved scenarios with their baseline period and scope", async () => {
    vi.spyOn(api, "listScenarios").mockResolvedValue({ items, total: 1, page: 1, page_size: 25 });

    render(<SavedScenariosPage />);

    expect(await screen.findByText("Downtime reduction 20%")).toBeInTheDocument();
    expect(screen.getByText("2026-07-01 to 2026-07-31")).toBeInTheDocument();
    expect(screen.getByText("Niger Delta Field")).toBeInTheDocument();
  });

  it("shows an empty state when there are no saved scenarios", async () => {
    vi.spyOn(api, "listScenarios").mockResolvedValue({ items: [], total: 0, page: 1, page_size: 25 });

    render(<SavedScenariosPage />);

    await waitFor(() => expect(screen.getByText("No saved scenarios yet.")).toBeInTheDocument());
  });

  it("disables Compare Selected until at least 2 scenarios are checked", async () => {
    vi.spyOn(api, "listScenarios").mockResolvedValue({ items, total: 1, page: 1, page_size: 25 });

    render(<SavedScenariosPage />);
    await screen.findByText("Downtime reduction 20%");

    const compareButton = screen.getByText(/Compare Selected/);
    expect(compareButton).toBeDisabled();
  });
});
