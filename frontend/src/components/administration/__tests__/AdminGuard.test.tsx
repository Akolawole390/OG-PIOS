import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AdminGuard } from "@/components/administration/AdminGuard";
import * as api from "@/lib/api";

describe("AdminGuard", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders children for an Administrator", async () => {
    vi.spyOn(api, "getCurrentUser").mockResolvedValue({
      id: 1, email: "admin@test.dev", full_name: "Admin", is_active: true, role_id: 1, role_name: "Administrator",
    });

    render(<AdminGuard><p>Protected content</p></AdminGuard>);

    expect(await screen.findByText("Protected content")).toBeInTheDocument();
  });

  it("shows an access-restricted message for a non-Administrator", async () => {
    vi.spyOn(api, "getCurrentUser").mockResolvedValue({
      id: 2, email: "viewer@test.dev", full_name: "Viewer", is_active: true, role_id: 7, role_name: "Viewer",
    });

    render(<AdminGuard><p>Protected content</p></AdminGuard>);

    expect(await screen.findByText("Access restricted")).toBeInTheDocument();
    expect(screen.queryByText("Protected content")).not.toBeInTheDocument();
  });

  it("shows an access-restricted message when the current-user lookup fails", async () => {
    vi.spyOn(api, "getCurrentUser").mockRejectedValue(new Error("401"));

    render(<AdminGuard><p>Protected content</p></AdminGuard>);

    await waitFor(() => expect(screen.getByText("Access restricted")).toBeInTheDocument());
  });
});
