import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { EquipmentForm } from "@/components/equipment/EquipmentForm";
import * as api from "@/lib/api";

describe("EquipmentForm", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "listFacilities").mockResolvedValue([
      { id: 1, name: "Facility A", facility_type: null, field_id: 1, field_name: "Field A" },
    ]);
    vi.spyOn(api, "listWells").mockResolvedValue({ items: [], total: 0, page: 1, page_size: 100 });
  });

  it("shows validation errors when required fields are missing", async () => {
    const onSubmit = vi.fn();
    render(<EquipmentForm submitLabel="Create Equipment" onSubmit={onSubmit} />);

    fireEvent.click(screen.getByRole("button", { name: /create equipment/i }));

    expect(await screen.findByText("Equipment tag is required.")).toBeInTheDocument();
    expect(screen.getByText("Name is required.")).toBeInTheDocument();
    expect(screen.getByText("Equipment type is required.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits an equipment payload with the expected shape", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<EquipmentForm submitLabel="Create Equipment" onSubmit={onSubmit} />);

    await waitFor(() => expect(screen.getByText("Facility A (Field A)")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText(/equipment tag/i), { target: { value: "COMP-01" } });
    fireEvent.change(screen.getByLabelText(/^name$/i), { target: { value: "Compressor 1" } });
    fireEvent.change(screen.getByLabelText(/equipment type/i), { target: { value: "compressor" } });
    fireEvent.change(screen.getByLabelText(/^facility$/i), { target: { value: "1" } });

    fireEvent.click(screen.getByRole("button", { name: /create equipment/i }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        equipment_tag: "COMP-01",
        name: "Compressor 1",
        equipment_type: "compressor",
        facility_id: 1,
        well_id: null,
      }),
    );
  });

  it("rejects negative operating hours", async () => {
    const onSubmit = vi.fn();
    render(<EquipmentForm submitLabel="Create Equipment" onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText(/equipment tag/i), { target: { value: "COMP-02" } });
    fireEvent.change(screen.getByLabelText(/^name$/i), { target: { value: "Compressor 2" } });
    fireEvent.change(screen.getByLabelText(/equipment type/i), { target: { value: "compressor" } });
    fireEvent.change(screen.getByLabelText(/operating hours/i), { target: { value: "-5" } });

    fireEvent.click(screen.getByRole("button", { name: /create equipment/i }));

    expect(await screen.findByText("Operating hours must be zero or a positive number.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
