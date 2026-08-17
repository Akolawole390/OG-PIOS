import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { UserForm } from "@/components/administration/UserForm";
import * as api from "@/lib/api";

const roles: api.Role[] = [
  { id: 1, name: "Administrator", description: null, user_count: 1 },
  { id: 6, name: "Analyst", description: null, user_count: 0 },
];

describe("UserForm", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "listRoles").mockResolvedValue(roles);
  });

  it("shows validation errors when required create fields are missing", async () => {
    const onSubmit = vi.fn();
    render(<UserForm mode="create" submitLabel="Create User" onSubmit={onSubmit} />);

    fireEvent.click(screen.getByRole("button", { name: /create user/i }));

    expect(await screen.findByText("Email is required.")).toBeInTheDocument();
    expect(screen.getByText("Full name is required.")).toBeInTheDocument();
    expect(screen.getByText("Password must be at least 8 characters.")).toBeInTheDocument();
    expect(screen.getByText("Role is required.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits a create payload with the expected shape", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<UserForm mode="create" submitLabel="Create User" onSubmit={onSubmit} />);

    await waitFor(() => expect(screen.getByText("Analyst")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "new@test.dev" } });
    fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: "New User" } });
    fireEvent.change(screen.getByLabelText(/temporary password/i), { target: { value: "supersecret1" } });
    fireEvent.change(screen.getByLabelText(/^role$/i), { target: { value: "6" } });

    fireEvent.click(screen.getByRole("button", { name: /create user/i }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        email: "new@test.dev",
        full_name: "New User",
        password: "supersecret1",
        role_id: 6,
        is_active: true,
      })
    );
  });

  it("never renders a password field in edit mode", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(
      <UserForm
        mode="edit"
        initialValues={{ full_name: "Existing User", role_id: "1", is_active: true }}
        submitLabel="Save Changes"
        onSubmit={onSubmit}
      />
    );

    await waitFor(() => expect(screen.getByText("Administrator")).toBeInTheDocument());
    expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument();
  });

  it("submits an edit payload without a password field", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(
      <UserForm
        mode="edit"
        initialValues={{ full_name: "Existing User", role_id: "1", is_active: true }}
        submitLabel="Save Changes"
        onSubmit={onSubmit}
      />
    );

    await waitFor(() => expect(screen.getByText("Administrator")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    const payload = onSubmit.mock.calls[0][0];
    expect(payload).not.toHaveProperty("password");
    expect(payload).not.toHaveProperty("email");
    expect(payload.full_name).toBe("Existing User");
  });
});
