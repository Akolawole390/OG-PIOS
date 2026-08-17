import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ReportFilterForm } from "@/components/reports/ReportFilterForm";
import * as api from "@/lib/api";

const mockFacility: api.Facility = {
  id: 1,
  name: "Facility A",
  facility_type: null,
  field_id: 1,
  field_name: "Field A",
};

describe("ReportFilterForm", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "listFacilities").mockResolvedValue([mockFacility]);
    vi.spyOn(api, "listWells").mockResolvedValue({ items: [], total: 0, page: 1, page_size: 200 });
    vi.spyOn(api, "listEquipment").mockResolvedValue({ items: [], total: 0, page: 1, page_size: 200 });
  });

  it("renders the full section-4 filter set", async () => {
    render(<ReportFilterForm value={{}} onChange={vi.fn()} />);

    await waitFor(() => expect(screen.getByText("Facility A (Field A)")).toBeInTheDocument());
    expect(screen.getByLabelText("Date From")).toBeInTheDocument();
    expect(screen.getByLabelText("Date To")).toBeInTheDocument();
    expect(screen.getByLabelText("Field")).toBeInTheDocument();
    expect(screen.getByLabelText("Commodity")).toBeInTheDocument();
    expect(screen.getByLabelText("Maintenance Type")).toBeInTheDocument();
    expect(screen.getByLabelText("Alert Severity")).toBeInTheDocument();
    expect(screen.getByLabelText("Production Loss Category")).toBeInTheDocument();
  });

  it("reports a date_from change", async () => {
    const onChange = vi.fn();
    render(<ReportFilterForm value={{}} onChange={onChange} />);

    fireEvent.change(screen.getByLabelText("Date From"), { target: { value: "2026-06-01" } });

    expect(onChange).toHaveBeenCalledWith({ date_from: "2026-06-01" });
  });

  it("reports an alert_severity change without touching other filters", async () => {
    const onChange = vi.fn();
    render(<ReportFilterForm value={{ field_id: 1 }} onChange={onChange} />);

    fireEvent.change(screen.getByLabelText("Alert Severity"), { target: { value: "critical" } });

    expect(onChange).toHaveBeenCalledWith({ field_id: 1, alert_severity: "critical" });
  });
});
