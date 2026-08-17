import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ComparisonTable } from "@/components/what-if/ComparisonTable";
import type { ComparisonRow } from "@/lib/api";

describe("ComparisonTable", () => {
  it("shows a placeholder when there are no rows", () => {
    render(<ComparisonTable rows={[]} />);
    expect(screen.getByText("No comparison data available.")).toBeInTheDocument();
  });

  it("renders baseline, scenario, difference, and % change for each metric", () => {
    const rows: ComparisonRow[] = [
      {
        metric: "Oil Production (bbl)",
        baseline: 1000,
        scenario: 1100,
        difference: 100,
        pct_change: 10,
        currency: null,
        direction: "positive",
      },
      {
        metric: "Operating Cost (USD)",
        baseline: 50000,
        scenario: 55000,
        difference: 5000,
        pct_change: 10,
        currency: "USD",
        direction: "negative",
      },
    ];
    render(<ComparisonTable rows={rows} />);

    expect(screen.getByText("Oil Production (bbl)")).toBeInTheDocument();
    expect(screen.getByText("1,000")).toBeInTheDocument();
    expect(screen.getByText("1,100")).toBeInTheDocument();
    expect(screen.getAllByText("+10.0%")).toHaveLength(2);

    expect(screen.getByText("Operating Cost (USD)")).toBeInTheDocument();
  });

  it("colors a cost increase as negative (a bad outcome) even though the difference is positive", () => {
    const rows: ComparisonRow[] = [
      {
        metric: "Operating Cost (USD)",
        baseline: 50000,
        scenario: 55000,
        difference: 5000,
        pct_change: 10,
        currency: "USD",
        direction: "negative",
      },
    ];
    render(<ComparisonTable rows={rows} />);

    const diffCell = screen.getByText(/\+\$5,000/);
    expect(diffCell.className).toContain("text-red-600");
  });

  it("shows an em dash for pct_change when the baseline is zero", () => {
    const rows: ComparisonRow[] = [
      {
        metric: "Downtime (hours)",
        baseline: 0,
        scenario: 0,
        difference: 0,
        pct_change: null,
        currency: null,
        direction: "neutral",
      },
    ];
    render(<ComparisonTable rows={rows} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});
