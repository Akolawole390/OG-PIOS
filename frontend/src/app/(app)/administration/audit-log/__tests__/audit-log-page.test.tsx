import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AuditLogPage from "@/app/(app)/administration/audit-log/page";
import * as api from "@/lib/api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/administration/audit-log",
}));

const adminUser: api.CurrentUser = {
  id: 1, email: "admin@test.dev", full_name: "Admin", is_active: true, role_id: 1, role_name: "Administrator",
};

const entries: api.AuditLogEntry[] = [
  {
    id: 1, action: "user_created", entity_type: "user", entity_id: 2, details: "Created user analyst@test.dev",
    status: "success", metadata_json: { role_id: 6 }, user_id: 1, user_email: "admin@test.dev",
    created_at: "2026-08-13T10:00:00Z",
  },
];

describe("AuditLogPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "getCurrentUser").mockResolvedValue(adminUser);
  });

  it("renders audit log entries", async () => {
    vi.spyOn(api, "listAuditLog").mockResolvedValue({ items: entries, total: 1, page: 1, page_size: 25 });

    render(<AuditLogPage />);

    const emailCell = await screen.findByText("admin@test.dev");
    expect(emailCell.closest("tr")).toHaveTextContent("User Created");
  });

  it("opens an event detail dialog on row click", async () => {
    vi.spyOn(api, "listAuditLog").mockResolvedValue({ items: entries, total: 1, page: 1, page_size: 25 });

    render(<AuditLogPage />);

    const emailCell = await screen.findByText("admin@test.dev");
    fireEvent.click(emailCell.closest("tr")!);

    expect(await screen.findByText("Event ID")).toBeInTheDocument();
    expect(screen.getByText("Created user analyst@test.dev")).toBeInTheDocument();
  });

  it("shows an empty state when there are no events", async () => {
    vi.spyOn(api, "listAuditLog").mockResolvedValue({ items: [], total: 0, page: 1, page_size: 25 });

    render(<AuditLogPage />);

    await waitFor(() => expect(screen.getByText("No audit events found.")).toBeInTheDocument());
  });
});
