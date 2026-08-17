import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BarChart } from "@/components/charts/BarChart";

describe("BarChart", () => {
  it("renders the title", () => {
    render(<BarChart title="Top Producing Wells" data={[]} />);
    expect(screen.getByText("Top Producing Wells")).toBeInTheDocument();
  });

  it("shows an empty state when there is no data", () => {
    render(<BarChart title="Top Producing Wells" data={[]} />);
    expect(screen.getByText("No data available yet.")).toBeInTheDocument();
  });

  it("does not show the empty state once data is provided", () => {
    render(
      <BarChart
        title="Top Producing Wells"
        data={[
          { key: "1", label: "NDF-01-001", value: 900 },
          { key: "2", label: "NDF-01-002", value: 400 },
        ]}
      />,
    );
    expect(screen.queryByText("No data available yet.")).not.toBeInTheDocument();
  });
});
