import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MaintenanceForm } from "@/components/maintenance/MaintenanceForm";
import * as api from "@/lib/api";

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
  operating_hours: null,
  next_maintenance_due: null,
  facility_id: null,
  well_id: null,
  field_id: null,
  field_name: null,
  facility_name: null,
  well_code: null,
  health_score: null,
  health_band: null,
  last_maintenance_date: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("MaintenanceForm", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "listEquipment").mockResolvedValue({ items: [mockEquipment], total: 1, page: 1, page_size: 200 });
    vi.spyOn(api, "listUsers").mockResolvedValue([
      { id: 5, email: "tech@ogpios.dev", full_name: "Demo Technician", is_active: true, role_id: 4, role_name: "Maintenance Engineer" },
    ]);
  });

  it("shows validation errors when required fields are missing", async () => {
    const onSubmit = vi.fn();
    render(<MaintenanceForm submitLabel="Create Work Order" onSubmit={onSubmit} />);

    fireEvent.click(screen.getByRole("button", { name: /create work order/i }));

    expect(await screen.findByText("Equipment is required.")).toBeInTheDocument();
    expect(screen.getByText("Maintenance type is required.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits a maintenance payload with the expected shape", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<MaintenanceForm submitLabel="Create Work Order" onSubmit={onSubmit} />);

    await waitFor(() => expect(screen.getByText("COMP-01 — Compressor 1")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText(/^equipment$/i), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText(/maintenance type/i), { target: { value: "preventive" } });
    fireEvent.change(screen.getByLabelText(/labor cost/i), { target: { value: "500" } });

    fireEvent.click(screen.getByRole("button", { name: /create work order/i }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ equipment_id: 1, maintenance_type: "preventive", labor_cost: 500 }),
    );
  });

  it("rejects a negative cost value", async () => {
    const onSubmit = vi.fn();
    render(<MaintenanceForm submitLabel="Create Work Order" onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText(/maintenance type/i), { target: { value: "corrective" } });
    await waitFor(() => expect(screen.getByText("COMP-01 — Compressor 1")).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText(/^equipment$/i), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText(/parts cost/i), { target: { value: "-10" } });

    fireEvent.click(screen.getByRole("button", { name: /create work order/i }));

    expect(await screen.findByText("Must be zero or a positive number.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
