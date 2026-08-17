import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import VerifyEmailPage from "@/app/verify-email/page";
import * as api from "@/lib/api";

let currentToken = "valid-token";

vi.mock("next/navigation", () => ({
  useSearchParams: () => ({ get: (key: string) => (key === "token" ? currentToken : null) }),
}));

describe("VerifyEmailPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    currentToken = "valid-token";
  });

  it("shows an error when no token is present in the URL", () => {
    currentToken = "";
    render(<VerifyEmailPage />);
    expect(screen.getByText(/missing its verification token/i)).toBeInTheDocument();
  });

  it("auto-verifies on mount and shows a success message", async () => {
    const verifySpy = vi.spyOn(api, "verifyEmail").mockResolvedValue({ message: "Email verified successfully." });

    render(<VerifyEmailPage />);

    expect(await screen.findByText(/your email has been verified/i)).toBeInTheDocument();
    expect(verifySpy).toHaveBeenCalledWith("valid-token");
  });

  it("shows an error message when verification fails", async () => {
    vi.spyOn(api, "verifyEmail").mockRejectedValue(new api.ApiError(400, "Invalid or expired verification link."));

    render(<VerifyEmailPage />);

    expect(await screen.findByText("Invalid or expired verification link.")).toBeInTheDocument();
  });
});
