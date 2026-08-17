import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ForgotPasswordPage from "@/app/forgot-password/page";
import * as api from "@/lib/api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/forgot-password",
}));

describe("ForgotPasswordPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("submits the email and shows the generic message", async () => {
    vi.spyOn(api, "forgotPassword").mockResolvedValue({
      message: "If an account exists for that email, a password reset link has been sent.",
      debug_token: null,
      debug_reset_url: null,
    });

    render(<ForgotPasswordPage />);
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "user@test.dev" } });
    fireEvent.click(screen.getByRole("button", { name: /send reset link/i }));

    expect(await screen.findByText(/a password reset link has been sent/i)).toBeInTheDocument();
    expect(screen.queryByText(/development mode/i)).not.toBeInTheDocument();
  });

  it("shows the dev-mode reset link when the backend returns one", async () => {
    vi.spyOn(api, "forgotPassword").mockResolvedValue({
      message: "If an account exists for that email, a password reset link has been sent.",
      debug_token: "abc123",
      debug_reset_url: "http://localhost:3000/reset-password?token=abc123",
    });

    render(<ForgotPasswordPage />);
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "user@test.dev" } });
    fireEvent.click(screen.getByRole("button", { name: /send reset link/i }));

    await waitFor(() => expect(screen.getByText(/development mode/i)).toBeInTheDocument());
    expect(screen.getByText("http://localhost:3000/reset-password?token=abc123")).toBeInTheDocument();
  });
});
