export type NavItem = {
  label: string;
  href: string;
};

export const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", href: "/dashboard" },
  { label: "Wells", href: "/wells" },
  { label: "Production", href: "/production" },
  { label: "Equipment", href: "/equipment" },
  { label: "Maintenance", href: "/maintenance" },
  { label: "Production Loss", href: "/production-loss" },
  { label: "Cost & Revenue", href: "/cost-revenue" },
  { label: "AI Insights", href: "/ai-insights" },
  { label: "Alerts", href: "/alerts" },
  { label: "What-If Simulator", href: "/what-if-simulator" },
  { label: "Reports", href: "/reports" },
  { label: "Administration", href: "/administration" },
];
