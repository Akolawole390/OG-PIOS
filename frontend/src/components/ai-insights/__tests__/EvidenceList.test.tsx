import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EvidenceList } from "@/components/ai-insights/EvidenceList";
import type { InsightEvidence } from "@/lib/api";

const evidence: InsightEvidence[] = [
  { id: 1, evidence_type: "observed_fact", description: "Production declined 18%.", source_type: "well", source_id: 1, source_label: "A-12", value: null, unit: null },
  { id: 2, evidence_type: "calculated_metric", description: "Estimated production loss is 500 barrels.", source_type: "computed", source_id: null, source_label: null, value: 500, unit: "bbl" },
  { id: 3, evidence_type: "possible_contributor", description: "ESP health deterioration may be associated with the decline.", source_type: "equipment", source_id: 2, source_label: "ESP-01", value: null, unit: null },
];

describe("EvidenceList", () => {
  it("groups evidence into visually distinct, labeled sections by type", () => {
    render(<EvidenceList evidence={evidence} />);

    expect(screen.getByText("Observed Facts")).toBeInTheDocument();
    expect(screen.getByText("Calculated Metrics")).toBeInTheDocument();
    expect(screen.getByText("Possible Contributors")).toBeInTheDocument();
    // Never has a "Correlations" section when no correlation-type evidence exists.
    expect(screen.queryByText("Correlations")).not.toBeInTheDocument();
  });

  it("never states causation for possible-contributor evidence", () => {
    render(<EvidenceList evidence={evidence} />);
    const contributorText = screen.getByText(/ESP health deterioration may be associated/);
    expect(contributorText.textContent).not.toMatch(/caused|the cause/i);
  });

  it("renders a value/unit badge for calculated metrics", () => {
    render(<EvidenceList evidence={evidence} />);
    expect(screen.getByText("(500 bbl)")).toBeInTheDocument();
  });

  it("shows a fallback message when there is no evidence", () => {
    render(<EvidenceList evidence={[]} />);
    expect(screen.getByText("No evidence recorded for this insight.")).toBeInTheDocument();
  });
});
