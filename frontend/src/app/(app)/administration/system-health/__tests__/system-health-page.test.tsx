import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import SystemHealthPage from "@/app/(app)/administration/system-health/page";
import * as api from "@/lib/api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/administration/system-health",
}));

const adminUser: api.CurrentUser = {
  id: 1, email: "admin@test.dev", full_name: "Admin", is_active: true, role_id: 1, role_name: "Administrator",
};

describe("SystemHealthPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "getCurrentUser").mockResolvedValue(adminUser);
  });

  it("renders status cards and AI configuration without ever showing a key", async () => {
    vi.spyOn(api, "getSystemHealth").mockResolvedValue({
      backend_status: "running",
      database_status: "connected",
      api_status: "ok",
      ai_provider_status: "not configured (using deterministic fallback)",
      app_version: "0.1.0",
      environment: "development",
    });
    vi.spyOn(api, "getAIConfig").mockResolvedValue({
      provider: "none",
      model: null,
      is_configured: false,
      status: "not configured — deterministic fallback active",
    });

    render(<SystemHealthPage />);

    expect(await screen.findByText("Backend")).toBeInTheDocument();
    expect(screen.getByText("Database")).toBeInTheDocument();
    expect(screen.getByText("0.1.0")).toBeInTheDocument();
    expect(screen.getByText(/API keys are configured server-side only/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/sk-/);
  });
});
