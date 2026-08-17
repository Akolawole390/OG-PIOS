import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { WellForm } from "@/components/wells/WellForm";
import * as api from "@/lib/api";

describe("WellForm", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "listFacilities").mockResolvedValue([
      { id: 1, name: "Facility A", facility_type: null, field_id: 1, field_name: "Field A" },
    ]);
  });

  it("shows validation errors when required fields are missing", async () => {
    const onSubmit = vi.fn();
    render(<WellForm submitLabel="Create Well" onSubmit={onSubmit} />);

    fireEvent.click(screen.getByRole("button", { name: /create well/i }));

    expect(await screen.findByText("Well ID is required.")).toBeInTheDocument();
    expect(screen.getByText("Name is required.")).toBeInTheDocument();
    expect(screen.getByText("Facility is required.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits a well payload with the expected shape", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<WellForm submitLabel="Create Well" onSubmit={onSubmit} />);

    await waitFor(() => expect(screen.getByText("Facility A (Field A)")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText(/well id/i), { target: { value: "NEW-001" } });
    fireEvent.change(screen.getByLabelText(/^name$/i), { target: { value: "New Well" } });
    fireEvent.change(screen.getByLabelText(/^facility$/i), { target: { value: "1" } });

    fireEvent.click(screen.getByRole("button", { name: /create well/i }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ well_id: "NEW-001", name: "New Well", facility_id: 1 }),
    );
  });

  it("rejects an out-of-range latitude", async () => {
    const onSubmit = vi.fn();
    render(<WellForm submitLabel="Create Well" onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText(/well id/i), { target: { value: "NEW-002" } });
    fireEvent.change(screen.getByLabelText(/^name$/i), { target: { value: "New Well" } });
    fireEvent.change(screen.getByLabelText(/latitude/i), { target: { value: "500" } });

    fireEvent.click(screen.getByRole("button", { name: /create well/i }));

    expect(await screen.findByText("Latitude must be between -90 and 90.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
