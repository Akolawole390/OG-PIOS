import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProductionLossForm } from "@/components/production-loss/ProductionLossForm";
import * as api from "@/lib/api";

const mockWell: api.Well = {
  id: 1,
  well_id: "PL-01",
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

describe("ProductionLossForm", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "listWells").mockResolvedValue({ items: [mockWell], total: 1, page: 1, page_size: 100 });
    vi.spyOn(api, "listEquipment").mockResolvedValue({ items: [], total: 0, page: 1, page_size: 200 });
  });

  it("shows a validation error when loss date is missing", async () => {
    const onSubmit = vi.fn();
    render(<ProductionLossForm submitLabel="Create Record" onSubmit={onSubmit} />);

    fireEvent.click(screen.getByRole("button", { name: /create record/i }));

    expect(await screen.findByText("Loss date is required.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits a production loss payload with the expected shape", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<ProductionLossForm submitLabel="Create Record" onSubmit={onSubmit} />);

    await waitFor(() => expect(screen.getByText("PL-01 — Test Well")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText(/loss date/i), { target: { value: "2026-01-15" } });
    fireEvent.change(screen.getByLabelText(/^well$/i), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText(/category/i), { target: { value: "weather" } });

    fireEvent.click(screen.getByRole("button", { name: /create record/i }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ loss_date: "2026-01-15", well_id: 1, category: "weather" }),
    );
  });

  it("rejects a non-numeric override value", async () => {
    const onSubmit = vi.fn();
    render(<ProductionLossForm submitLabel="Create Record" onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText(/loss date/i), { target: { value: "2026-01-15" } });
    fireEvent.change(screen.getByLabelText(/oil lost/i), { target: { value: "not-a-number" } });

    fireEvent.click(screen.getByRole("button", { name: /create record/i }));

    expect(await screen.findByText("Must be a number.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
