import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AlertsPage from "@/app/(app)/alerts/page";
import * as api from "@/lib/api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/alerts",
}));

const mockAlert: api.AlertEntry = {
  id: 1,
  alert_type: "equipment_critical_health",
  category: "equipment",
  source_module: "equipment",
  severity: "critical",
  status: "new",
  title: "ESP-01 — Critical Equipment Health",
  description: "ESP-01's health score is 18.0, below the critical threshold of 25.",
  recommended_action: "Prioritize inspection.",
  notes: null,
  well_id: null,
  well_code: null,
  field_id: 1,
  field_name: "Field A",
  facility_id: null,
  facility_name: null,
  equipment_id: 1,
  equipment_tag: "ESP-01",
  maintenance_record_id: null,
  maintenance_work_order_number: null,
  production_loss_id: null,
  threshold_value: 25,
  current_value: 18,
  unit: "score",
  dedup_key: "equipment_critical_health:equipment:1",
  occurrence_count: 1,
  triggered_at: "2026-08-01T00:00:00Z",
  last_detected_at: "2026-08-01T00:00:00Z",
  acknowledged_at: null,
  resolved_at: null,
  acknowledged_by_name: null,
  resolved_by_name: null,
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-01T00:00:00Z",
  disclaimer_text: "Rule-based alert — not a guaranteed conclusion or autonomous action.",
};

describe("AlertsPage (Alert Center dashboard)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "getCurrentUser").mockResolvedValue({
      id: 1,
      email: "admin@ogpios.dev",
      full_name: "Admin",
      is_active: true,
      role_id: 1,
      role_name: "Administrator",
    });
    vi.spyOn(api, "getAlertSummary").mockResolvedValue({
      total: 5,
      open_count: 3,
      by_severity: { critical: 1, high: 1, medium: 1, low: 1, informational: 1 },
      by_status: { new: 3, acknowledged: 1, investigating: 0, resolved: 1, dismissed: 0 },
      by_category: [{ category: "equipment", count: 2 }],
      by_field: [{ key: "1", label: "Field A", count: 2 }],
      by_equipment: [{ key: "1", label: "ESP-01", count: 1 }],
      recent: [mockAlert],
      disclaimer_text: "Rule-based alert — not a guaranteed conclusion or autonomous action.",
    });
  });

  it("renders KPI counts, the recent alert list, and the disclaimer", async () => {
    render(<AlertsPage />);

    await waitFor(() => expect(screen.getByText("Alert Center")).toBeInTheDocument());
    expect(await screen.findByText("ESP-01 — Critical Equipment Health")).toBeInTheDocument();
    expect(screen.getByText("Rule-based alert — not a guaranteed conclusion or autonomous action.")).toBeInTheDocument();
    expect(screen.getByText("Run Rules")).toBeInTheDocument();
  });

  it("hides the Run Rules button for a non-Administrator", async () => {
    vi.spyOn(api, "getCurrentUser").mockResolvedValue({
      id: 2,
      email: "analyst@ogpios.dev",
      full_name: "Analyst",
      is_active: true,
      role_id: 6,
      role_name: "Analyst",
    });

    render(<AlertsPage />);

    await waitFor(() => expect(screen.getByText("Alert Center")).toBeInTheDocument());
    await waitFor(() => expect(screen.queryByText("Run Rules")).not.toBeInTheDocument());
  });
});
