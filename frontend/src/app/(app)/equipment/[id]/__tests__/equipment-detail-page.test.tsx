import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import EquipmentDetailPage from "@/app/(app)/equipment/[id]/page";
import * as api from "@/lib/api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/equipment/1",
  useParams: () => ({ id: "1" }),
  useRouter: () => ({ push: vi.fn() }),
}));

const mockEquipment: api.Equipment = {
  id: 1,
  equipment_tag: "COMP-01",
  name: "Compressor 1",
  equipment_type: "compressor",
  manufacturer: "Baker Hughes",
  model: "Model-100",
  serial_number: "SN-1",
  installation_date: "2024-01-01",
  commissioning_date: "2024-01-15",
  description: "Synthetic demo equipment.",
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

const mockHealth: api.EquipmentHealth = {
  equipment_id: 1,
  score: 92,
  band: "Excellent",
  starting_score: 100,
  factors: [],
  disclaimer_text: "Rule-based health indicator — not a failure prediction.",
  computed_at: "2026-01-01T00:00:00Z",
};

describe("EquipmentDetailPage", () => {
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
    vi.spyOn(api, "getEquipment").mockResolvedValue(mockEquipment);
    vi.spyOn(api, "getEquipmentHealth").mockResolvedValue(mockHealth);
    vi.spyOn(api, "getEquipmentDowntime").mockResolvedValue({
      events: [],
      summary: { event_count: 0, total_hours: 0 },
    });
    vi.spyOn(api, "getEquipmentMaintenance").mockResolvedValue({
      records: [],
      summary: { record_count: 0, total_cost: 0, total_downtime_hours: 0 },
    });
    vi.spyOn(api, "getEquipmentReliability").mockResolvedValue({
      equipment_id: 1,
      mtbf_hours: null,
      mtbf_data_sufficient: false,
      mttr_hours: null,
      mttr_data_sufficient: false,
      availability_pct: 100,
      failure_count: 0,
      failure_count_annualized: null,
      observation_period_hours: 8760,
      disclaimer_text: "Foundational reliability estimate — not a certified analysis.",
      assumptions: [],
      computed_at: "2026-01-01T00:00:00Z",
    });
    vi.spyOn(api, "listEquipmentReadings").mockResolvedValue({ items: [], total: 0 });
    vi.spyOn(api, "listProductionLoss").mockResolvedValue({ items: [], total: 0, page: 1, page_size: 10 });
  });

  it("renders equipment overview and health breakdown", async () => {
    render(<EquipmentDetailPage />);

    await waitFor(() => expect(screen.getByText("Compressor 1")).toBeInTheDocument(), { timeout: 2000 });
    expect(screen.getByText(/COMP-01/)).toBeInTheDocument();
    expect(screen.getAllByText("Excellent").length).toBeGreaterThan(0);
    expect(screen.getByText(/Rule-based health indicator/)).toBeInTheDocument();
    expect(screen.getByText("Edit")).toBeInTheDocument();
  });

  it("hides Edit/Delete controls for a Viewer", async () => {
    vi.spyOn(api, "getCurrentUser").mockResolvedValue({
      id: 2,
      email: "viewer@ogpios.dev",
      full_name: "Viewer",
      is_active: true,
      role_id: 7,
      role_name: "Viewer",
    });

    render(<EquipmentDetailPage />);

    await waitFor(() => expect(screen.getByText("Compressor 1")).toBeInTheDocument(), { timeout: 2000 });
    expect(screen.queryByText("Edit")).not.toBeInTheDocument();
    expect(screen.queryByText("Delete")).not.toBeInTheDocument();
  });
});
