import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PermissionMatrixTable } from "@/components/administration/PermissionMatrixTable";
import type { PermissionMatrixEntry } from "@/lib/api";

const entries: PermissionMatrixEntry[] = [
  { module: "Wells", action: "View", roles: ["Administrator", "Analyst"], note: null },
  { module: "Wells", action: "Delete", roles: [], note: "Not implemented — no delete endpoint exists for wells." },
  { module: "Administration", action: "Manage Users", roles: ["Administrator"], note: null },
];

describe("PermissionMatrixTable", () => {
  it("groups entries by module and renders role badges", () => {
    render(<PermissionMatrixTable entries={entries} />);

    expect(screen.getByText("Wells")).toBeInTheDocument();
    expect(screen.getByText("Administration")).toBeInTheDocument();
    expect(screen.getByText("View")).toBeInTheDocument();
    expect(screen.getByText("Manage Users")).toBeInTheDocument();
    expect(screen.getAllByText("Administrator").length).toBeGreaterThanOrEqual(2);
  });

  it("shows a note instead of role badges when an action has no roles", () => {
    render(<PermissionMatrixTable entries={entries} />);

    expect(screen.getByText("Not implemented — no delete endpoint exists for wells.")).toBeInTheDocument();
  });
});
