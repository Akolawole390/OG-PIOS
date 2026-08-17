import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AlertDetailPage from "@/app/(app)/alerts/[id]/page";
import * as api from "@/lib/api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/alerts/1",
  useParams: () => ({ id: "1" }),
  useRouter: () => ({ push: vi.fn() }),
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
  recommended_action: "Prioritize inspection and maintenance.",
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

describe("AlertDetailPage", () => {
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
    vi.spyOn(api, "getAlert").mockResolvedValue(mockAlert);
    vi.spyOn(api, "getAlertHistory").mockResolvedValue({
      items: [{ id: 1, from_state: null, to_state: "new", note: null, changed_by_name: null, changed_at: "2026-08-01T00:00:00Z" }],
    });
  });

  it("renders alert detail, trigger condition, and history", async () => {
    render(<AlertDetailPage />);

    await waitFor(() => expect(screen.getByText("ESP-01 — Critical Equipment Health")).toBeInTheDocument());
    expect(screen.getByText(/health score is 18\.0/)).toBeInTheDocument();
    expect(screen.getByText("Created (new)")).toBeInTheDocument();
    expect(screen.getByText("Acknowledge")).toBeInTheDocument();
  });

  it("acknowledges the alert and reloads its state", async () => {
    const acknowledgeSpy = vi.spyOn(api, "acknowledgeAlert").mockResolvedValue({ ...mockAlert, status: "acknowledged" });

    render(<AlertDetailPage />);
    await waitFor(() => expect(screen.getByText("ESP-01 — Critical Equipment Health")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /^acknowledge$/i }));

    await waitFor(() => expect(acknowledgeSpy).toHaveBeenCalledWith(1, undefined));
  });

  it("hides action buttons for a Viewer", async () => {
    vi.spyOn(api, "getCurrentUser").mockResolvedValue({
      id: 2,
      email: "viewer@ogpios.dev",
      full_name: "Viewer",
      is_active: true,
      role_id: 7,
      role_name: "Viewer",
    });

    render(<AlertDetailPage />);

    await waitFor(() => expect(screen.getByText("ESP-01 — Critical Equipment Health")).toBeInTheDocument());
    expect(screen.queryByText("Acknowledge")).not.toBeInTheDocument();
  });
});
