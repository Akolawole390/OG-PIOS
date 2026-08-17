import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProductionForm } from "@/components/production/ProductionForm";
import * as api from "@/lib/api";

const mockWell: api.Well = {
  id: 1,
  well_id: "NDF-01-001",
  name: "NDF Well 001",
  well_type: null,
  status: "active",
  artificial_lift_type: null,
  latitude: null,
  longitude: null,
  completion_date: null,
  completion_type: null,
  total_depth_ft: null,
  facility_id: 1,
  facility: { id: 1, name: "Facility A", facility_type: null, field: { id: 1, name: "Field A" } },
  created_at: "",
  updated_at: "",
};

describe("ProductionForm", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "listWells").mockResolvedValue({ items: [mockWell], total: 1, page: 1, page_size: 100 });
  });

  it("shows validation errors when required fields are missing", async () => {
    const onSubmit = vi.fn();
    const onSaved = vi.fn();
    render(<ProductionForm submitLabel="Create Record" onSubmit={onSubmit} onSaved={onSaved} />);

    fireEvent.click(screen.getByRole("button", { name: /create record/i }));

    expect(await screen.findByText("Well is required.")).toBeInTheDocument();
    expect(screen.getByText("Date is required.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits a payload with the expected shape and calls onSaved when there are no warnings", async () => {
    const onSubmit = vi.fn().mockResolvedValue({ id: 42, warnings: null });
    const onSaved = vi.fn();
    render(<ProductionForm submitLabel="Create Record" onSubmit={onSubmit} onSaved={onSaved} />);

    await waitFor(() => expect(screen.getByText("NDF-01-001 — NDF Well 001")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText(/^well$/i), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText(/^date$/i), { target: { value: "2026-06-01" } });
    fireEvent.change(screen.getByLabelText(/oil \(bopd\)/i), { target: { value: "500" } });

    fireEvent.click(screen.getByRole("button", { name: /create record/i }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ well_id: 1, record_date: "2026-06-01", oil_bopd: 500 }),
    );
    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(42));
  });

  it("shows warnings and waits for Continue instead of auto-navigating", async () => {
    const onSubmit = vi.fn().mockResolvedValue({ id: 42, warnings: ["Oil rate is unusually high — please verify."] });
    const onSaved = vi.fn();
    render(<ProductionForm submitLabel="Create Record" onSubmit={onSubmit} onSaved={onSaved} />);

    await waitFor(() => expect(screen.getByText("NDF-01-001 — NDF Well 001")).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText(/^well$/i), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText(/^date$/i), { target: { value: "2026-06-01" } });

    fireEvent.click(screen.getByRole("button", { name: /create record/i }));

    expect(await screen.findByText(/unusually high/i)).toBeInTheDocument();
    expect(onSaved).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: /continue/i }));
    expect(onSaved).toHaveBeenCalledWith(42);
  });

  it("rejects negative oil production", async () => {
    const onSubmit = vi.fn();
    render(<ProductionForm submitLabel="Create Record" onSubmit={onSubmit} onSaved={vi.fn()} />);

    await waitFor(() => expect(screen.getByText("NDF-01-001 — NDF Well 001")).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText(/^well$/i), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText(/^date$/i), { target: { value: "2026-06-01" } });
    fireEvent.change(screen.getByLabelText(/oil \(bopd\)/i), { target: { value: "-10" } });

    fireEvent.click(screen.getByRole("button", { name: /create record/i }));

    expect(await screen.findByText("Must be zero or a positive number.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
