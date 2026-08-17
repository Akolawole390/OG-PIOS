import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { OperatingCostForm } from "@/components/cost-revenue/OperatingCostForm";
import * as api from "@/lib/api";

const mockFacility: api.Facility = {
  id: 1,
  name: "Facility A",
  facility_type: null,
  field_id: 1,
  field_name: "Field A",
};

describe("OperatingCostForm", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "listFacilities").mockResolvedValue([mockFacility]);
    vi.spyOn(api, "listWells").mockResolvedValue({ items: [], total: 0, page: 1, page_size: 100 });
    vi.spyOn(api, "listEquipment").mockResolvedValue({ items: [], total: 0, page: 1, page_size: 200 });
  });

  it("shows validation errors when required fields are missing", async () => {
    const onSubmit = vi.fn();
    render(<OperatingCostForm submitLabel="Create Cost" onSubmit={onSubmit} />);

    fireEvent.click(screen.getByRole("button", { name: /create cost/i }));

    expect(await screen.findByText("Cost date is required.")).toBeInTheDocument();
    expect(screen.getByText("Category is required.")).toBeInTheDocument();
    expect(screen.getByText("Amount is required and must be a number.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("rejects a negative amount", async () => {
    const onSubmit = vi.fn();
    render(<OperatingCostForm submitLabel="Create Cost" onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText(/cost date/i), { target: { value: "2026-02-01" } });
    fireEvent.change(screen.getByLabelText(/category/i), { target: { value: "Energy" } });
    fireEvent.change(screen.getByLabelText(/amount/i), { target: { value: "-50" } });

    fireEvent.click(screen.getByRole("button", { name: /create cost/i }));

    expect(await screen.findByText("Amount cannot be negative.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits an operating cost payload with the expected shape", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<OperatingCostForm submitLabel="Create Cost" onSubmit={onSubmit} />);

    await waitFor(() => expect(screen.getByText("Facility A (Field A)")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText(/cost date/i), { target: { value: "2026-02-01" } });
    fireEvent.change(screen.getByLabelText(/category/i), { target: { value: "Energy" } });
    fireEvent.change(screen.getByLabelText(/amount/i), { target: { value: "1250.5" } });
    fireEvent.change(screen.getByLabelText(/currency/i), { target: { value: "NGN" } });

    fireEvent.click(screen.getByRole("button", { name: /create cost/i }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        cost_date: "2026-02-01",
        category: "Energy",
        amount: 1250.5,
        currency: "NGN",
        field_id: null,
        facility_id: null,
        well_id: null,
        equipment_id: null,
      }),
    );
  });
});
