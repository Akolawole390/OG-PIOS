"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { TargetForm } from "@/components/production/TargetForm";
import {
  createProductionTarget,
  deleteProductionTarget,
  getCurrentUser,
  listProductionTargets,
  type CurrentUser,
  type ProductionTarget,
  type ProductionTargetPayload,
} from "@/lib/api";

const CAN_MANAGE = new Set(["Administrator", "Production Engineer"]);

export default function ProductionTargetsPage() {
  const [targets, setTargets] = useState<ProductionTarget[]>([]);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [error, setError] = useState<string | null>(null);

  function refresh() {
    listProductionTargets().then(setTargets).catch(() => setError("Unable to load targets."));
  }

  useEffect(() => {
    refresh();
    getCurrentUser().then(setCurrentUser).catch(() => undefined);
  }, []);

  async function handleCreate(payload: ProductionTargetPayload) {
    await createProductionTarget(payload);
    refresh();
  }

  async function handleDelete(id: number) {
    await deleteProductionTarget(id);
    refresh();
  }

  const canManage = currentUser ? CAN_MANAGE.has(currentUser.role_name) : false;

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader title="Production Targets" description="Per-well production rate targets, used for the actual-vs-target chart and target variance KPI." />

      {error ? <p className="text-sm text-red-600 dark:text-red-400">{error}</p> : null}

      {canManage ? <TargetForm onSubmit={handleCreate} /> : null}

      <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-zinc-200 bg-zinc-50 text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
              <th className="px-4 py-2 font-medium">Well</th>
              <th className="px-4 py-2 font-medium">Effective Date</th>
              <th className="px-4 py-2 font-medium">Oil Target (BOPD)</th>
              <th className="px-4 py-2 font-medium">Gas Target (MSCFD)</th>
              <th className="px-4 py-2 font-medium">Water Target (BWPD)</th>
              {canManage ? <th className="px-4 py-2 font-medium">Actions</th> : null}
            </tr>
          </thead>
          <tbody>
            {targets.length === 0 ? (
              <tr>
                <td colSpan={canManage ? 6 : 5} className="px-4 py-6 text-center text-zinc-500 dark:text-zinc-400">
                  No targets configured.
                </td>
              </tr>
            ) : (
              targets.map((target) => (
                <tr key={target.id} className="border-b border-zinc-100 last:border-0 dark:border-zinc-900">
                  <td className="px-4 py-2 text-zinc-900 dark:text-zinc-50">{target.well_code}</td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">{target.effective_date}</td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">{target.oil_target_bopd ?? "—"}</td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">{target.gas_target_mscfd ?? "—"}</td>
                  <td className="px-4 py-2 text-zinc-700 dark:text-zinc-300">{target.water_target_bwpd ?? "—"}</td>
                  {canManage ? (
                    <td className="px-4 py-2">
                      <button
                        type="button"
                        onClick={() => handleDelete(target.id)}
                        className="text-xs font-medium text-red-600 hover:underline dark:text-red-400"
                      >
                        Delete
                      </button>
                    </td>
                  ) : null}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
