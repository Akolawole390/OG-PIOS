import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DailyOperationsBriefPage from "@/app/(app)/ai-insights/daily-brief/page";
import * as api from "@/lib/api";

const BRIEF: api.DailyBrief = {
  generated_at: "2026-01-15T08:00:00Z",
  period_label: "2026-01-01 to 2026-01-15",
  sections: [{ title: "1. Production Performance", summary: "Oil: 1,000 bbl.", items: ["Target variance: -3.0%"] }],
  narrative: null,
  disclaimer_text: "AI-generated estimate requiring engineering review; not a guaranteed conclusion.",
};

describe("DailyOperationsBriefPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } });
  });

  it("renders the brief and copies it to the clipboard", async () => {
    vi.spyOn(api, "getDailyBrief").mockResolvedValue(BRIEF);

    render(<DailyOperationsBriefPage />);
    expect(await screen.findByText("1. Production Performance")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /^copy$/i }));

    expect(await screen.findByText(/copied to clipboard/i)).toBeInTheDocument();
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(expect.stringContaining("1. Production Performance"));
  });

  it("exports the brief as a PDF", async () => {
    vi.spyOn(api, "getDailyBrief").mockResolvedValue(BRIEF);
    vi.spyOn(api, "exportDailyBriefPdf").mockResolvedValue(undefined);

    render(<DailyOperationsBriefPage />);
    await screen.findByText("1. Production Performance");

    fireEvent.click(screen.getByRole("button", { name: /export pdf/i }));

    expect(api.exportDailyBriefPdf).toHaveBeenCalledWith(false);
  });
});
