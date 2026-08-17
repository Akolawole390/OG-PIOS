"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { MultiCurrencyAmount } from "@/components/cost-revenue/MultiCurrencyAmount";
import {
  getUnitEconomics,
  listFacilities,
  listWells,
  type Facility,
  type UnitEconomics,
  type Well,
} from "@/lib/api";

function formatNumber(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString(undefined, { maximumFractionDigits: digits });
}

export default function UnitEconomicsPage() {
  const [facilityId, setFacilityId] = useState("");
  const [wellId, setWellId] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [wells, setWells] = useState<Well[]>([]);
  const [data, setData] = useState<UnitEconomics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listFacilities().then(setFacilities).catch(() => undefined);
    listWells({ page_size: 100, sort: "well_id" }).then((res) => setWells(res.items)).catch(() => undefined);
  }, []);

  useEffect(() => {
    getUnitEconomics({
      facility_id: facilityId ? Number(facilityId) : undefined,
      well_id: wellId ? Number(wellId) : undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
    })
      .then(setData)
      .catch(() => setError("Unable to load unit economics for this selection."));
  }, [facilityId, wellId, dateFrom, dateTo]);

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title="Unit Economics"
        description="Cost and revenue per barrel/BOE — calculated only where the underlying production and price data support it."
      />

      <div className="flex flex-wrap items-center gap-3">
        <select value={facilityId} onChange={(e) => setFacilityId(e.target.value)} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          <option value="">All facilities</option>
          {facilities.map((f) => (
            <option key={f.id} value={f.id}>{f.name}</option>
          ))}
        </select>
        <select value={wellId} onChange={(e) => setWellId(e.target.value)} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          <option value="">All wells</option>
          {wells.map((w) => (
            <option key={w.id} value={w.id}>{w.well_id}</option>
          ))}
        </select>
        <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900" />
        <span className="text-sm text-zinc-400">to</span>
        <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900" />
      </div>

      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

      {data ? (
        <>
          <p className="text-xs text-zinc-500 dark:text-zinc-400">
            Period: {data.period_start} to {data.period_end}
          </p>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <KpiCard label="Oil Production" value={formatNumber(data.production.oil_bbl)} unit="bbl" />
            <KpiCard label="Gas Production" value={formatNumber(data.production.gas_mscf)} unit="mscf" />
            <KpiCard label="BOE" value={formatNumber(data.production.boe)} unit="boe" calculated />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <MoneyBlock label="Cost per Barrel" amounts={data.economics.cost_per_bbl} />
            <MoneyBlock label="Cost per BOE" amounts={data.economics.cost_per_boe} />
            <MoneyBlock label="Revenue per Barrel" amounts={data.economics.revenue_per_bbl} />
            <MoneyBlock label="Revenue per BOE" amounts={data.economics.revenue_per_boe} />
            <MoneyBlock label="Estimated Operating Margin" amounts={data.economics.margin} />
          </div>

          {data.economics.currency_mismatch ? (
            <p className="rounded-md border border-amber-300 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
              Revenue and cost for this selection are in different currencies — margin is intentionally left blank
              rather than computed with an invented exchange rate.
            </p>
          ) : null}

          <p className="text-xs text-zinc-400 dark:text-zinc-500">{data.disclaimer_text}</p>
        </>
      ) : (
        <p className="text-sm text-zinc-500 dark:text-zinc-400">Loading…</p>
      )}
    </div>
  );
}

function MoneyBlock({ label, amounts }: { label: string; amounts: { currency: string; amount: number }[] }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <p className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">{label}</p>
      <p className="mt-2 text-lg font-semibold text-zinc-900 dark:text-zinc-50">
        <MultiCurrencyAmount amounts={amounts} emptyLabel="Not computable" />
      </p>
    </div>
  );
}
