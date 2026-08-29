import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import InvestigateEventPage from "@/app/(app)/ai-insights/investigate/page";
import * as api from "@/lib/api";

let searchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useSearchParams: () => searchParams,
}));

const RESULT: api.InvestigationResult = {
  event: "Well PBF-03-003 underperforming",
  impact_summary: "120.0 bopd",
  primary_contributor: "PBF-03-003",
  possible_causes: [{ description: "Open alert: Wellhead pressure low (high)", evidence_type: "correlation" }],
  ai_assessment: "No AI provider is configured — showing the deterministic evidence gathered above only.",
  confidence_level: "medium",
  recommended_investigation: "Review the possible causes below on-site.",
  sources: [{ source_type: "well", source_id: 1, source_label: "PBF-03-003" }],
  answered_by: "deterministic",
  disclaimer_text: "AI-generated estimate requiring engineering review; not a guaranteed conclusion.",
};

describe("InvestigateEventPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    searchParams = new URLSearchParams();
  });

  it("investigates a manually entered well id and renders the structured result", async () => {
    vi.spyOn(api, "investigateEvent").mockResolvedValue(RESULT);

    render(<InvestigateEventPage />);
    fireEvent.change(screen.getByLabelText(/well id/i), { target: { value: "1" } });
    fireEvent.click(screen.getByRole("button", { name: /^investigate$/i }));

    expect(await screen.findByText("Well PBF-03-003 underperforming")).toBeInTheDocument();
    expect(api.investigateEvent).toHaveBeenCalledWith({ well_id: 1 });
    expect(screen.getByText(/open alert: wellhead pressure low/i)).toBeInTheDocument();
  });

  it("auto-investigates when an insight_id is present in the URL", async () => {
    searchParams = new URLSearchParams("insight_id=5");
    vi.spyOn(api, "investigateEvent").mockResolvedValue(RESULT);

    render(<InvestigateEventPage />);

    await waitFor(() => expect(api.investigateEvent).toHaveBeenCalledWith({ insight_id: 5 }));
    expect(await screen.findByText("Well PBF-03-003 underperforming")).toBeInTheDocument();
  });

  it("shows an error message when no target is entered", async () => {
    render(<InvestigateEventPage />);
    fireEvent.click(screen.getByRole("button", { name: /^investigate$/i }));

    expect(await screen.findByText(/enter an insight id, well id, or equipment id/i)).toBeInTheDocument();
  });
});
