import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ScenarioComparisonCharts } from "@/components/what-if/ScenarioComparisonCharts";
import type { ComparisonRow } from "@/lib/api";

describe("ScenarioComparisonCharts", () => {
  it("shows a placeholder when there are no rows", () => {
    render(<ScenarioComparisonCharts rows={[]} />);
    expect(screen.getByText("No comparison data available.")).toBeInTheDocument();
  });

  it("renders one tile per comparison metric, with a shared Baseline/Scenario legend", () => {
    const rows: ComparisonRow[] = [
      { metric: "Oil Production (bbl)", baseline: 1000, scenario: 1100, difference: 100, pct_change: 10, currency: null, direction: "positive" },
      { metric: "Operating Cost (USD)", baseline: 50000, scenario: 55000, difference: 5000, pct_change: 10, currency: "USD", direction: "negative" },
    ];
    render(<ScenarioComparisonCharts rows={rows} />);

    expect(screen.getByText("Oil Production (bbl)")).toBeInTheDocument();
    expect(screen.getByText("Operating Cost (USD)")).toBeInTheDocument();
    expect(screen.getByText("Baseline")).toBeInTheDocument();
    expect(screen.getByText("Scenario")).toBeInTheDocument();
  });

  it("shows the percent change as a delta annotation per tile", () => {
    const rows: ComparisonRow[] = [
      { metric: "Oil Production (bbl)", baseline: 1000, scenario: 1100, difference: 100, pct_change: 10, currency: null, direction: "positive" },
    ];
    render(<ScenarioComparisonCharts rows={rows} />);

    expect(screen.getByText(/\+10\.0%/)).toBeInTheDocument();
  });

  it("shows 'No change' when pct_change is null", () => {
    const rows: ComparisonRow[] = [
      { metric: "Downtime (hours)", baseline: 0, scenario: 0, difference: 0, pct_change: null, currency: null, direction: "neutral" },
    ];
    render(<ScenarioComparisonCharts rows={rows} />);

    expect(screen.getByText(/No change/)).toBeInTheDocument();
  });
});
