import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AssumptionForm } from "@/components/what-if/AssumptionForm";
import type { ScenarioAssumptions } from "@/lib/api";

describe("AssumptionForm", () => {
  it("renders every scenario variable grouped by section, all blank by default", () => {
    render(<AssumptionForm values={{}} onChange={vi.fn()} />);

    expect(screen.getByText("Production")).toBeInTheDocument();
    expect(screen.getByText("Downtime")).toBeInTheDocument();
    expect(screen.getByText("Production Loss")).toBeInTheDocument();
    expect(screen.getByText("Cost")).toBeInTheDocument();
    expect(screen.getByText("Commodity Price")).toBeInTheDocument();

    const productionInput = screen.getByLabelText(/production change/i) as HTMLInputElement;
    expect(productionInput.value).toBe("");
  });

  it("reports a numeric change for a single lever without touching the others", () => {
    const onChange = vi.fn();
    render(<AssumptionForm values={{}} onChange={onChange} />);

    fireEvent.change(screen.getByLabelText(/downtime change/i), { target: { value: "-20" } });

    expect(onChange).toHaveBeenCalledWith({ downtime_change_pct: -20 });
  });

  it("clears a field back to null when emptied, preserving other set values", () => {
    const onChange = vi.fn();
    const values: ScenarioAssumptions = { production_change_pct: 10, downtime_change_pct: -20 };
    render(<AssumptionForm values={values} onChange={onChange} />);

    fireEvent.change(screen.getByLabelText(/downtime change/i), { target: { value: "" } });

    expect(onChange).toHaveBeenCalledWith({ production_change_pct: 10, downtime_change_pct: null });
  });

  it("accepts a decimal price override", () => {
    const onChange = vi.fn();
    render(<AssumptionForm values={{}} onChange={onChange} />);

    fireEvent.change(screen.getByLabelText(/^oil price override/i), { target: { value: "82.5" } });

    expect(onChange).toHaveBeenCalledWith({ oil_price_override: 82.5 });
  });

  it("disables every input when disabled is set", () => {
    render(<AssumptionForm values={{}} onChange={vi.fn()} disabled />);

    const productionInput = screen.getByLabelText(/production change/i) as HTMLInputElement;
    expect(productionInput).toBeDisabled();
  });
});
