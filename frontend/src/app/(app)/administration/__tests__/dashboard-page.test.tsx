import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AdministrationPage from "@/app/(app)/administration/page";
import * as api from "@/lib/api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/administration",
}));

const adminUser: api.CurrentUser = {
  id: 1, email: "admin@test.dev", full_name: "Admin", is_active: true, role_id: 1, role_name: "Administrator",
};

const dashboard: api.AdminDashboard = {
  total_users: 4,
  active_users: 3,
  inactive_users: 1,
  roles: [
    { role_name: "Administrator", user_count: 1 },
    { role_name: "Analyst", user_count: 0 },
  ],
  recent_activity: [
    { id: 1, action: "user_created", entity_type: "user", user_email: "admin@test.dev", status: "success", created_at: "2026-08-13T10:00:00Z" },
  ],
  system_status: "operational",
  configuration_status: "ok",
  ai_provider_configured: false,
};

describe("AdministrationPage (dashboard)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "getCurrentUser").mockResolvedValue(adminUser);
  });

  it("renders dashboard KPIs for an Administrator", async () => {
    vi.spyOn(api, "getAdminDashboard").mockResolvedValue(dashboard);

    render(<AdministrationPage />);

    expect(await screen.findByText("Total Users")).toBeInTheDocument();
    expect(screen.getAllByText("4").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Not configured")).toBeInTheDocument();
  });

  it("renders recent administrative activity", async () => {
    vi.spyOn(api, "getAdminDashboard").mockResolvedValue(dashboard);

    render(<AdministrationPage />);

    expect(await screen.findByText(/User Created/)).toBeInTheDocument();
  });

  it("denies access to a non-Administrator", async () => {
    vi.spyOn(api, "getCurrentUser").mockResolvedValue({ ...adminUser, role_name: "Viewer" });
    vi.spyOn(api, "getAdminDashboard").mockResolvedValue(dashboard);

    render(<AdministrationPage />);

    await waitFor(() => expect(screen.getByText("Access restricted")).toBeInTheDocument());
    expect(screen.queryByText("Total Users")).not.toBeInTheDocument();
  });
});
