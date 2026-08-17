import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ResetPasswordPage from "@/app/reset-password/page";
import * as api from "@/lib/api";

let currentToken = "valid-token";

vi.mock("next/navigation", () => ({
  useSearchParams: () => ({ get: (key: string) => (key === "token" ? currentToken : null) }),
}));

describe("ResetPasswordPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    currentToken = "valid-token";
  });

  it("shows an error when no token is present in the URL", () => {
    currentToken = "";
    render(<ResetPasswordPage />);
    expect(screen.getByText(/missing its reset token/i)).toBeInTheDocument();
  });

  it("rejects mismatched passwords client-side without calling the API", () => {
    const resetSpy = vi.spyOn(api, "resetPassword");
    render(<ResetPasswordPage />);

    fireEvent.change(screen.getByLabelText(/^new password$/i), { target: { value: "password123" } });
    fireEvent.change(screen.getByLabelText(/confirm new password/i), { target: { value: "different123" } });
    fireEvent.click(screen.getByRole("button", { name: /reset password/i }));

    expect(screen.getByText(/do not match/i)).toBeInTheDocument();
    expect(resetSpy).not.toHaveBeenCalled();
  });

  it("submits the token and new password, then shows a success state", async () => {
    const resetSpy = vi.spyOn(api, "resetPassword").mockResolvedValue({ message: "Password reset successfully." });

    render(<ResetPasswordPage />);
    fireEvent.change(screen.getByLabelText(/^new password$/i), { target: { value: "password123" } });
    fireEvent.change(screen.getByLabelText(/confirm new password/i), { target: { value: "password123" } });
    fireEvent.click(screen.getByRole("button", { name: /reset password/i }));

    await waitFor(() => expect(resetSpy).toHaveBeenCalledWith("valid-token", "password123"));
    expect(await screen.findByText(/you can now log in/i)).toBeInTheDocument();
  });

  it("shows the backend's error message on failure", async () => {
    vi.spyOn(api, "resetPassword").mockRejectedValue(new api.ApiError(400, "Invalid or expired reset link."));

    render(<ResetPasswordPage />);
    fireEvent.change(screen.getByLabelText(/^new password$/i), { target: { value: "password123" } });
    fireEvent.change(screen.getByLabelText(/confirm new password/i), { target: { value: "password123" } });
    fireEvent.click(screen.getByRole("button", { name: /reset password/i }));

    expect(await screen.findByText("Invalid or expired reset link.")).toBeInTheDocument();
  });
});
