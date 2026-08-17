import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ReportSectionToggles } from "@/components/reports/ReportSectionToggles";

describe("ReportSectionToggles", () => {
  it("renders one checkbox per available section, checked when selected", () => {
    render(
      <ReportSectionToggles
        available={["production", "equipment", "alerts"]}
        selected={["production", "alerts"]}
        onChange={vi.fn()}
      />,
    );

    expect((screen.getByLabelText("Production") as HTMLInputElement).checked).toBe(true);
    expect((screen.getByLabelText("Equipment") as HTMLInputElement).checked).toBe(false);
    expect((screen.getByLabelText("Alerts") as HTMLInputElement).checked).toBe(true);
  });

  it("adds a section to the selection when toggled on", () => {
    const onChange = vi.fn();
    render(<ReportSectionToggles available={["production", "equipment"]} selected={["production"]} onChange={onChange} />);

    fireEvent.click(screen.getByLabelText("Equipment"));

    expect(onChange).toHaveBeenCalledWith(["production", "equipment"]);
  });

  it("removes a section from the selection when toggled off", () => {
    const onChange = vi.fn();
    render(<ReportSectionToggles available={["production", "equipment"]} selected={["production", "equipment"]} onChange={onChange} />);

    fireEvent.click(screen.getByLabelText("Production"));

    expect(onChange).toHaveBeenCalledWith(["equipment"]);
  });
});
