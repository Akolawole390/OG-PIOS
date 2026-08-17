import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ChangePasswordPage from "@/app/(app)/account/change-password/page";
import * as api from "@/lib/api";

describe("ChangePasswordPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("rejects a too-short new password client-side without calling the API", () => {
    const changeSpy = vi.spyOn(api, "changePassword");
    render(<ChangePasswordPage />);

    fireEvent.change(screen.getByLabelText(/current password/i), { target: { value: "oldpassword1" } });
    fireEvent.change(screen.getByLabelText(/^new password$/i), { target: { value: "short" } });
    fireEvent.change(screen.getByLabelText(/confirm new password/i), { target: { value: "short" } });
    fireEvent.click(screen.getByRole("button", { name: /change password/i }));

    expect(screen.getByText(/at least 8 characters/i)).toBeInTheDocument();
    expect(changeSpy).not.toHaveBeenCalled();
  });

  it("rejects mismatched new passwords client-side without calling the API", () => {
    const changeSpy = vi.spyOn(api, "changePassword");
    render(<ChangePasswordPage />);

    fireEvent.change(screen.getByLabelText(/current password/i), { target: { value: "oldpassword1" } });
    fireEvent.change(screen.getByLabelText(/^new password$/i), { target: { value: "newpassword1" } });
    fireEvent.change(screen.getByLabelText(/confirm new password/i), { target: { value: "different1" } });
    fireEvent.click(screen.getByRole("button", { name: /change password/i }));

    expect(screen.getByText(/do not match/i)).toBeInTheDocument();
    expect(changeSpy).not.toHaveBeenCalled();
  });

  it("submits current and new password and shows a success message", async () => {
    const changeSpy = vi.spyOn(api, "changePassword").mockResolvedValue({ message: "Password changed successfully." });

    render(<ChangePasswordPage />);
    fireEvent.change(screen.getByLabelText(/current password/i), { target: { value: "oldpassword1" } });
    fireEvent.change(screen.getByLabelText(/^new password$/i), { target: { value: "newpassword1" } });
    fireEvent.change(screen.getByLabelText(/confirm new password/i), { target: { value: "newpassword1" } });
    fireEvent.click(screen.getByRole("button", { name: /change password/i }));

    await waitFor(() =>
      expect(changeSpy).toHaveBeenCalledWith({ current_password: "oldpassword1", new_password: "newpassword1" })
    );
    expect(await screen.findByText("Password changed successfully.")).toBeInTheDocument();
  });

  it("shows the backend's error message when the current password is wrong", async () => {
    vi.spyOn(api, "changePassword").mockRejectedValue(new api.ApiError(400, "Current password is incorrect"));

    render(<ChangePasswordPage />);
    fireEvent.change(screen.getByLabelText(/current password/i), { target: { value: "wrongpassword" } });
    fireEvent.change(screen.getByLabelText(/^new password$/i), { target: { value: "newpassword1" } });
    fireEvent.change(screen.getByLabelText(/confirm new password/i), { target: { value: "newpassword1" } });
    fireEvent.click(screen.getByRole("button", { name: /change password/i }));

    expect(await screen.findByText("Current password is incorrect")).toBeInTheDocument();
  });
});
