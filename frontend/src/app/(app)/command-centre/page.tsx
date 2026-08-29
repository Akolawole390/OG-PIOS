"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { PageHeader } from "@/components/layout/PageHeader";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { FieldStatusRow, type FieldStatusItem, type FieldStatusLevel } from "@/components/command-centre/FieldStatusRow";
import { OperationsScoreCard } from "@/components/command-centre/OperationsScoreCard";
import { WellHealthList } from "@/components/command-centre/WellHealthList";
import { EquipmentHealthList } from "@/components/command-centre/EquipmentHealthList";
import { AskOgPiosPanel } from "@/components/command-centre/AskOgPiosPanel";
import {
  getAlertSummary,
  getEquipmentDashboard,
  getEquipmentIssues,
  getInsightSummary,
  getMaintenanceDashboard,
  getProductionIssues,
  getProductionKpis,
  type AlertSummaryResponse,
  type EquipmentDashboard,
  type EquipmentIssuesResponse,
  type InsightSummary,
  type MaintenanceDashboard,
  type ProductionIssuesResponse,
  type ProductionKpis,
} from "@/lib/api";

function formatNumber(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString(undefined, { maximumFractionDigits: digits });
}

// Production score: 100 at/above target, sliding down as the shortfall grows. Deliberately a
// simple linear estimate, not a statistical model — see OperationsScoreCard's disclaimer.
function productionScore(kpis: ProductionKpis | null): number | null {
  if (!kpis || kpis.target_variance_pct === null || kpis.target_variance_pct === undefined) return null;
  return Math.max(0, Math.min(100, Math.round(100 + kpis.target_variance_pct * 2)));
}

function productionLevel(kpis: ProductionKpis | null): FieldStatusLevel {
  const score = productionScore(kpis);
  if (score === null) return "not_tracked";
  if (score >= 95) return "normal";
  if (score >= 85) return "attention";
  if (score >= 70) return "warning";
  return "critical";
}

function equipmentScore(equipment: EquipmentDashboard | null): number | null {
  if (!equipment || equipment.status_counts.total === 0) return null;
  const { total, failed, attention_count } = equipment.status_counts;
  return Math.max(0, Math.min(100, Math.round(((total - failed - attention_count) / total) * 100)));
}

function equipmentLevel(equipment: EquipmentDashboard | null): FieldStatusLevel {
  if (!equipment || equipment.status_counts.total === 0) return "not_tracked";
  if (equipment.status_counts.failed > 0) return "critical";
  if (equipment.status_counts.attention_count > 0) return "warning";
  return "normal";
}

function maintenanceScore(maintenance: MaintenanceDashboard | null): number | null {
  if (!maintenance) return null;
  return Math.max(0, 100 - maintenance.status_counts.computed_overdue_count * 10);
}

function maintenanceLevel(maintenance: MaintenanceDashboard | null): FieldStatusLevel {
  if (!maintenance) return "not_tracked";
  const overdue = maintenance.status_counts.computed_overdue_count;
  if (overdue >= 3) return "critical";
  if (overdue >= 1) return "warning";
  if (maintenance.status_counts.emergency_count > 0) return "warning";
  return "normal";
}

export default function CommandCentrePage() {
  const [kpis, setKpis] = useState<ProductionKpis | null>(null);
  const [equipment, setEquipment] = useState<EquipmentDashboard | null>(null);
  const [maintenance, setMaintenance] = useState<MaintenanceDashboard | null>(null);
  const [alertSummary, setAlertSummary] = useState<AlertSummaryResponse | null>(null);
  const [insightSummary, setInsightSummary] = useState<InsightSummary | null>(null);
  const [productionIssues, setProductionIssues] = useState<ProductionIssuesResponse | null>(null);
  const [equipmentIssues, setEquipmentIssues] = useState<EquipmentIssuesResponse | null>(null);

  useEffect(() => {
    getProductionKpis().then(setKpis).catch(() => undefined);
    getEquipmentDashboard().then(setEquipment).catch(() => undefined);
    getMaintenanceDashboard().then(setMaintenance).catch(() => undefined);
    getAlertSummary().then(setAlertSummary).catch(() => undefined);
    getInsightSummary().then(setInsightSummary).catch(() => undefined);
    getProductionIssues().then(setProductionIssues).catch(() => undefined);
    getEquipmentIssues({ limit: 6 }).then(setEquipmentIssues).catch(() => undefined);
  }, []);

  const fieldStatusItems: FieldStatusItem[] = [
    { label: "Production", level: productionLevel(kpis) },
    { label: "Equipment", level: equipmentLevel(equipment) },
    { label: "Maintenance", level: maintenanceLevel(maintenance) },
    { label: "HSE", level: "not_tracked", hint: "Not yet tracked in OG-PIOS" },
    { label: "Energy", level: "not_tracked", hint: "Not yet tracked in OG-PIOS" },
  ];

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title="AI Command Centre"
        description="Field-wide operational status, AI insights, and decision support — aggregated from Production, Equipment, Maintenance, Alerts, and AI Insights."
      />

      <FieldStatusRow items={fieldStatusItems} />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <OperationsScoreCard
          subScores={[
            { label: "Production", score: productionScore(kpis) },
            { label: "Equipment", score: equipmentScore(equipment) },
            { label: "Maintenance", score: maintenanceScore(maintenance) },
          ]}
        />
        <Link href="/alerts" className="block">
          <KpiCard
            label="Active Alerts"
            value={formatNumber(alertSummary?.open_count, 0)}
            hint={alertSummary ? `${alertSummary.by_severity.critical} critical — view Alert Center` : "View Alert Center"}
          />
        </Link>
        <Link href="/ai-insights" className="block">
          <KpiCard
            label="Open AI Insights"
            value={formatNumber(insightSummary?.open_count, 0)}
            hint={insightSummary ? `${insightSummary.by_severity.critical} critical — view AI Insights` : "View AI Insights"}
          />
        </Link>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <WellHealthList
          downWells={productionIssues?.down_wells ?? []}
          zeroProductionWells={productionIssues?.zero_production_wells ?? []}
        />
        <EquipmentHealthList items={equipmentIssues?.items ?? []} />
      </div>

      <AskOgPiosPanel />

      {alertSummary?.disclaimer_text ? (
        <p className="text-xs text-zinc-400 dark:text-zinc-500">{alertSummary.disclaimer_text}</p>
      ) : null}
    </div>
  );
}
