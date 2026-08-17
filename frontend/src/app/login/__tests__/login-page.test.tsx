import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import LoginPage from "@/app/login/page";
import * as api from "@/lib/api";

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

describe("LoginPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    pushMock.mockClear();
  });

  it("renders email/password fields and a forgot-password link", () => {
    render(<LoginPage />);

    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    const link = screen.getByText("Forgot password?");
    expect(link.closest("a")).toHaveAttribute("href", "/forgot-password");
  });

  it("shows a pilot/synthetic-data badge", () => {
    render(<LoginPage />);

    expect(screen.getByText("PILOT · SYNTHETIC DATA")).toBeInTheDocument();
  });

  it("logs in and redirects to the dashboard on success", async () => {
    const loginSpy = vi.spyOn(api, "login").mockResolvedValue(undefined);

    render(<LoginPage />);
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "admin@ogpios.dev" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "password123" } });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => expect(loginSpy).toHaveBeenCalledWith("admin@ogpios.dev", "password123"));
    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/dashboard"));
  });

  it("shows an error message when login fails", async () => {
    vi.spyOn(api, "login").mockRejectedValue(new api.ApiError(401, "Incorrect email or password"));

    render(<LoginPage />);
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "admin@ogpios.dev" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "wrong" } });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText(/unable to sign in/i)).toBeInTheDocument();
    expect(pushMock).not.toHaveBeenCalled();
  });
});
