import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AiOperationsAssistantPage from "@/app/(app)/ai-insights/assistant/page";
import * as api from "@/lib/api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/ai-insights/assistant",
}));

describe("AiOperationsAssistantPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("sends a question and renders the deterministic answer with sources", async () => {
    const askSpy = vi.spyOn(api, "askAssistant").mockResolvedValue({
      answer: "4 equipment item(s) require attention: ESP-01.",
      sources: [{ source_type: "equipment", source_id: 1, source_label: "ESP-01" }],
      answered_by: "deterministic",
      disclaimer_text: "Rule-based estimate.",
    });

    render(<AiOperationsAssistantPage />);

    fireEvent.click(screen.getByRole("button", { name: /which equipment requires attention/i }));

    await waitFor(() => expect(askSpy).toHaveBeenCalledWith("Which equipment requires attention?"));
    expect(await screen.findByText(/4 equipment item\(s\) require attention/)).toBeInTheDocument();
    expect(screen.getByText("From OG-PIOS data")).toBeInTheDocument();
    expect(screen.getByText(/Sources: ESP-01/)).toBeInTheDocument();
  });

  it("submits a typed question via the input form", async () => {
    const askSpy = vi.spyOn(api, "askAssistant").mockResolvedValue({
      answer: "Custom answer.",
      sources: [],
      answered_by: "ai",
      disclaimer_text: "Rule-based estimate.",
    });

    render(<AiOperationsAssistantPage />);

    fireEvent.change(screen.getByPlaceholderText(/ask a question/i), { target: { value: "Why is well X underperforming?" } });
    fireEvent.click(screen.getByRole("button", { name: /^ask$/i }));

    await waitFor(() => expect(askSpy).toHaveBeenCalledWith("Why is well X underperforming?"));
    expect(await screen.findByText("Custom answer.")).toBeInTheDocument();
    expect(screen.getByText("AI-interpreted")).toBeInTheDocument();
  });

  it("shows an error message when the assistant call fails", async () => {
    vi.spyOn(api, "askAssistant").mockRejectedValue(new Error("429"));

    render(<AiOperationsAssistantPage />);
    fireEvent.click(screen.getByRole("button", { name: /which equipment requires attention/i }));

    expect(await screen.findByText(/unable to reach the assistant/i)).toBeInTheDocument();
  });
});
