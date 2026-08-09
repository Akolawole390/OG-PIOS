import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Sidebar } from "@/components/navigation/Sidebar";
import { NAV_ITEMS } from "@/config/navigation";

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
}));

describe("Sidebar", () => {
  it("renders every navigation label", () => {
    render(<Sidebar />);

    for (const item of NAV_ITEMS) {
      expect(screen.getByText(item.label)).toBeInTheDocument();
    }
  });
});
