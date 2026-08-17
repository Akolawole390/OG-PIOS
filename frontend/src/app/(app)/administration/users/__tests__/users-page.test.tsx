import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AdministrationUsersPage from "@/app/(app)/administration/users/page";
import * as api from "@/lib/api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/administration/users",
}));

const adminUser: api.CurrentUser = {
  id: 1, email: "admin@test.dev", full_name: "Admin", is_active: true, role_id: 1, role_name: "Administrator",
};

const users: api.User[] = [
  {
    id: 2, email: "analyst@test.dev", full_name: "Ada Analyst", is_active: true, role_id: 6, role_name: "Analyst",
    created_at: "2026-08-01T00:00:00Z", updated_at: "2026-08-01T00:00:00Z",
  },
];

describe("AdministrationUsersPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "getCurrentUser").mockResolvedValue(adminUser);
    vi.spyOn(api, "listRoles").mockResolvedValue([
      { id: 1, name: "Administrator", description: null, user_count: 1 },
      { id: 6, name: "Analyst", description: null, user_count: 1 },
    ]);
  });

  it("renders users with their role and status", async () => {
    vi.spyOn(api, "listAdministrationUsers").mockResolvedValue({ items: users, total: 1, page: 1, page_size: 20 });

    render(<AdministrationUsersPage />);

    const nameLink = await screen.findByText("Ada Analyst");
    expect(screen.getByText("analyst@test.dev")).toBeInTheDocument();
    const row = nameLink.closest("tr")!;
    expect(within(row).getByText("Active")).toBeInTheDocument();
  });

  it("deactivates a user when the toggle button is clicked", async () => {
    vi.spyOn(api, "listAdministrationUsers").mockResolvedValue({ items: users, total: 1, page: 1, page_size: 20 });
    const updateUser = vi.spyOn(api, "updateUser").mockResolvedValue({ ...users[0], is_active: false });

    render(<AdministrationUsersPage />);

    const button = await screen.findByRole("button", { name: /deactivate/i });
    fireEvent.click(button);

    await waitFor(() => expect(updateUser).toHaveBeenCalledWith(2, { is_active: false }));
  });

  it("shows an empty state when there are no users", async () => {
    vi.spyOn(api, "listAdministrationUsers").mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 });

    render(<AdministrationUsersPage />);

    await waitFor(() => expect(screen.getByText("No users found.")).toBeInTheDocument());
  });
});
