import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ImportPreviewTable } from "@/components/production/ImportPreviewTable";
import type { ImportRowResult } from "@/lib/api";

const rows: ImportRowResult[] = [
  {
    row_number: 2,
    status: "valid",
    well_id: "NDF-01-001",
    record_date: "2026-06-01",
    parsed: { oil_bopd: 500 },
    messages: [],
    existing_record_id: null,
  },
  {
    row_number: 3,
    status: "duplicate",
    well_id: "NDF-01-001",
    record_date: "2026-06-02",
    parsed: { oil_bopd: 400 },
    messages: ["A record already exists for this well and date."],
    existing_record_id: 7,
  },
  {
    row_number: 4,
    status: "invalid",
    well_id: "BOGUS",
    record_date: "2026-06-03",
    parsed: { oil_bopd: 100 },
    messages: ["Unrecognized well_id 'BOGUS'."],
    existing_record_id: null,
  },
];

describe("ImportPreviewTable", () => {
  it("renders status badges and messages for every row", () => {
    render(
      <ImportPreviewTable rows={rows} actions={{}} onActionChange={vi.fn()} onBulkDuplicateAction={vi.fn()} />,
    );

    expect(screen.getByText("valid")).toBeInTheDocument();
    expect(screen.getByText("duplicate")).toBeInTheDocument();
    expect(screen.getByText("invalid")).toBeInTheDocument();
    expect(screen.getByText("Unrecognized well_id 'BOGUS'.")).toBeInTheDocument();
    expect(screen.getByText("Excluded")).toBeInTheDocument();
  });

  it("calls onActionChange when a duplicate row's action select changes", () => {
    const onActionChange = vi.fn();
    render(
      <ImportPreviewTable rows={rows} actions={{}} onActionChange={onActionChange} onBulkDuplicateAction={vi.fn()} />,
    );

    fireEvent.change(screen.getByDisplayValue("Skip"), { target: { value: "overwrite" } });
    expect(onActionChange).toHaveBeenCalledWith(3, "overwrite");
  });

  it("calls onBulkDuplicateAction from the Skip All / Overwrite All buttons", () => {
    const onBulkDuplicateAction = vi.fn();
    render(
      <ImportPreviewTable rows={rows} actions={{}} onActionChange={vi.fn()} onBulkDuplicateAction={onBulkDuplicateAction} />,
    );

    fireEvent.click(screen.getByRole("button", { name: /overwrite all/i }));
    expect(onBulkDuplicateAction).toHaveBeenCalledWith("overwrite");
  });
});
