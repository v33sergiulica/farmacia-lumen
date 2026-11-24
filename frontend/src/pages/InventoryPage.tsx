import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useInventory } from "../api/client";
import { ChartTooltip } from "../components/ChartTooltip";
import { KpiCard } from "../components/KpiCard";
import { PanelError } from "../components/PanelError";
import {
  ChartCardSkeleton,
  KpiStripSkeleton,
  TableCardSkeleton,
} from "../components/Skeletons";
import { useFilters } from "../context/FilterContext";
import {
  formatCompactRon,
  formatInt,
  formatPct,
  formatRon,
  shortStoreName,
} from "../utils/format";

export function InventoryPage() {
  const { filters } = useFilters();
  const [skuView, setSkuView] = useState<"stockouts" | "slow">("stockouts");
  const { data, isLoading, isPlaceholderData, isError, error, refetch } =
    useInventory(filters, 50);

  if (isError && !data) {
    return (
      <PanelError
        title="Unable to load Inventory & Restock Risk"
        message={error instanceof Error ? error.message : "Request failed"}
        onRetry={() => void refetch()}
      />
    );
  }

  const kpis = data?.kpis;
  const cadenceChart = data
    ? data.store_cadence.map((s) => ({
        ...s,
        label: `${shortStoreName(s.store_name)} (${s.last_delivery_date?.slice(5) ?? "—"})`,
      }))
    : [];

  return (
    <div
      className={`space-y-5 transition-opacity duration-150 ${
        isPlaceholderData ? "opacity-60" : "opacity-100"
      }`}
    >
      {/* Explicit Data-Honesty Banner */}
      <div className="rounded-lg border border-[#B7DFC9] bg-[#ECF6F0] px-4 py-2.5 text-xs text-[#111A16]">
        <span className="font-semibold text-[#146C43]">
          Snapshot as of {data?.snapshot_date ?? "2026-10-31"} — date range filter does not apply.
        </span>{" "}
        <span className="text-[#46544D]">
          Region, Pharmacy, and Category filters remain active. Velocity &amp; revenue at risk cover the 90 days ending{" "}
          <span className="font-mono-data">{data?.snapshot_date ?? "2026-10-31"}</span> (from{" "}
          <span className="font-mono-data">{data?.velocity_window_start ?? "2026-08-03"}</span>); inactive SKU #180 and closed store Deva #16 are excluded.
        </span>
      </div>

      {isLoading || !kpis ? (
        <KpiStripSkeleton count={5} />
      ) : (
        <section className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <KpiCard
            label="Open-Store Stock Value"
            value={formatCompactRon(kpis.total_inv_cost_ron)}
            unit="RON"
            subtext={`${formatInt(kpis.total_units)} units at cost`}
          />
          <KpiCard
            label="Active Zero-Stock Pairs"
            value={formatInt(kpis.active_zero_stock_pairs)}
            delta={`of ${formatInt(kpis.open_store_sku_pairs)} pairs`}
            tone="danger"
            subtext="p.activ = 1 in open stores"
          />
          <KpiCard
            label="90-Day Revenue at Risk"
            value={formatCompactRon(kpis.rev_90d_at_risk_ron)}
            unit="RON"
            tone="danger"
            delta="On zero-stock pairs"
            subtext="Ex-VAT 90d trailing sales"
          />
          <KpiCard
            label="Thin Safety Stock (1–5)"
            value={formatPct(kpis.low_stock_share_pct, 1)}
            delta={`${formatInt(kpis.low_stock_pairs)} pairs`}
            tone="warning"
            subtext={`Dead 90d: ${kpis.dead_stock_90d_pairs} pairs (${formatRon(kpis.dead_stock_90d_cost_ron)} RON)`}
          />
          <KpiCard
            label="Ledger Discrepancy"
            value={formatInt(kpis.ledger_discrepancy_units)}
            unit="units"
            delta="Receptii − Vanzari"
            tone={kpis.ledger_discrepancy_units === 0 ? "positive" : "danger"}
            subtext="Exact ledger balance"
          />
        </section>
      )}

      {/* Store Delivery-Cadence vs Zero-Stock Chart */}
      {isLoading || !data ? (
        <ChartCardSkeleton heightClass="h-80" />
      ) : (
        <section className="rounded-lg border border-[#E2E7E4] bg-white p-5">
          <h2 className="text-balance text-sm font-semibold text-[#111A16]">
            Zero-Stock Active SKUs by Pharmacy &amp; Last Delivery Date (MM-DD)
          </h2>
          <p className="mt-0.5 text-xs text-[#5C6B63]">
            Stores restocked earliest in the final week (Oct 26–27) carry the highest zero-stock counts (crimson = 15+ active SKUs out)
          </p>

          <div className="mt-4 h-96 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={cadenceChart}
                margin={{ top: 8, right: 16, left: 0, bottom: 52 }}
              >
                <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="#E2E7E4" />
                <XAxis
                  dataKey="label"
                  tick={{ fill: "#5C6B63", fontSize: 10 }}
                  interval={0}
                  angle={-32}
                  textAnchor="end"
                  height={92}
                  axisLine={{ stroke: "#E2E7E4" }}
                  tickLine={false}
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fill: "#5C6B63", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  width={36}
                />
                <Tooltip content={<ChartTooltip unitMode="mixed" />} />
                <Bar
                  dataKey="zero_active_skus"
                  name="Zero-Stock SKUs"
                  radius={[3, 3, 0, 0]}
                  maxBarSize={26}
                >
                  {cadenceChart.map((s) => (
                    <Cell
                      key={s.store_id}
                      fill={
                        s.zero_active_skus >= 15
                          ? "#B42318"
                          : s.zero_active_skus >= 10
                            ? "#B54708"
                            : "#146C43"
                      }
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      {/* Priority Restock & Transfer Queue */}
      {isLoading || !data ? (
        <TableCardSkeleton rows={10} />
      ) : (
        <section className="rounded-lg border border-[#E2E7E4] bg-white p-5">
          <h2 className="text-balance text-sm font-semibold text-[#111A16]">
            Priority Restock &amp; Intra-Chain Transfer Queue (Top {data.stockout_queue.length})
          </h2>
          <p className="mt-0.5 text-xs text-[#5C6B63]">
            Ranked by trailing 90-day revenue at risk (RON fără TVA) with highest-surplus donor pharmacy
          </p>

          <div className="mt-4 overflow-x-auto">
            <table className="w-full border-collapse text-left text-xs">
              <thead className="border-b border-[#E2E7E4] text-[#5C6B63]">
                <tr>
                  <th className="py-2 pr-2 font-medium">SKU</th>
                  <th className="py-2 pr-2 font-medium">Product</th>
                  <th className="py-2 pr-2 font-medium">Pharmacy</th>
                  <th className="py-2 pr-2 font-medium">Last Delivery</th>
                  <th className="py-2 pl-2 text-right font-medium">90d Units</th>
                  <th className="py-2 pl-2 text-right font-medium">90d Rev at Risk</th>
                  <th className="py-2 pl-3 font-medium">Recommended Transfer Donor</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E2E7E4]">
                {data.stockout_queue.slice(0, 25).map((item) => (
                  <tr
                    key={`${item.store_id}-${item.product_id}`}
                    className="hover:bg-[#F6F7F6]"
                  >
                    <td className="font-mono-data py-2 pr-2 text-[#5C6B63]">
                      #{item.product_id}
                    </td>
                    <td className="py-2 pr-2 font-medium text-[#111A16]">
                      {item.product_name}
                    </td>
                    <td className="py-2 pr-2 text-[#46544D]">
                      #{item.store_id} {shortStoreName(item.store_name)}
                    </td>
                    <td className="font-mono-data py-2 pr-2 text-[#5C6B63]">
                      {item.last_delivery_date ?? "—"}
                    </td>
                    <td className="tabular py-2 pl-2 text-right text-[#46544D]">
                      {formatInt(item.qty_90d)}
                    </td>
                    <td className="tabular py-2 pl-2 text-right font-semibold text-[#B42318]">
                      {formatRon(item.rev_90d_at_risk_ron)} RON
                    </td>
                    <td className="py-2 pl-3 text-[#146C43]">
                      {item.suggested_transfer_from ? (
                        <span>
                          {shortStoreName(item.suggested_transfer_from.store_name)} (
                          <span className="tabular font-medium">
                            {item.suggested_transfer_from.available_stoc} u
                          </span>
                          {item.suggested_transfer_from.same_region ? " · same region" : ""})
                        </span>
                      ) : (
                        <span className="text-[#5C6B63]">Direct supplier order</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* SKU Summary Toggle: Most Stocked-Out vs Slow Movers */}
      {data && (
        <section className="rounded-lg border border-[#E2E7E4] bg-white p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-balance text-sm font-semibold text-[#111A16]">
                {skuView === "stockouts"
                  ? "Most Stocked-Out Active SKUs Across Chain"
                  : "Slowest-Moving Inventory (Highest Days of Supply)"}
              </h2>
            </div>
            <div className="inline-flex rounded-lg border border-[#E2E7E4] bg-[#F6F7F6] p-1">
              {(
                [
                  { id: "stockouts", label: "Top Stocked-Out SKUs" },
                  { id: "slow", label: "Slow Movers (DOS)" },
                ] as const
              ).map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setSkuView(tab.id)}
                  className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                    skuView === tab.id
                      ? "bg-white text-[#146C43] ring-1 ring-[#E2E7E4]"
                      : "text-[#46544D] hover:text-[#111A16]"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          <div className="mt-4 overflow-x-auto">
            {skuView === "stockouts" ? (
              <table className="w-full border-collapse text-left text-xs">
                <thead className="border-b border-[#E2E7E4] text-[#5C6B63]">
                  <tr>
                    <th className="py-2 pr-2 font-medium">SKU</th>
                    <th className="py-2 pr-2 font-medium">Product</th>
                    <th className="py-2 pr-2 font-medium">Category</th>
                    <th className="py-2 pl-2 text-right font-medium">Zero Stores</th>
                    <th className="py-2 pl-2 text-right font-medium">Chain Stock</th>
                    <th className="py-2 pl-2 text-right font-medium">90d Units</th>
                    <th className="py-2 pl-2 text-right font-medium">90d Revenue</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E2E7E4]">
                  {data.top_stocked_out_skus.map((s) => (
                    <tr key={s.product_id} className="hover:bg-[#F6F7F6]">
                      <td className="font-mono-data py-2 pr-2 text-[#5C6B63]">
                        #{s.product_id}
                      </td>
                      <td className="py-2 pr-2 font-medium text-[#111A16]">
                        {s.product_name}
                      </td>
                      <td className="py-2 pr-2 text-[#46544D]">{s.category}</td>
                      <td className="tabular py-2 pl-2 text-right font-semibold text-[#B42318]">
                        {s.zero_stores}
                      </td>
                      <td className="tabular py-2 pl-2 text-right text-[#46544D]">
                        {formatInt(s.total_stoc)}
                      </td>
                      <td className="tabular py-2 pl-2 text-right text-[#46544D]">
                        {formatInt(s.qty_90d)}
                      </td>
                      <td className="tabular py-2 pl-2 text-right font-medium text-[#111A16]">
                        {formatRon(s.rev_90d_ron)} RON
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <table className="w-full border-collapse text-left text-xs">
                <thead className="border-b border-[#E2E7E4] text-[#5C6B63]">
                  <tr>
                    <th className="py-2 pr-2 font-medium">SKU</th>
                    <th className="py-2 pr-2 font-medium">Product</th>
                    <th className="py-2 pr-2 font-medium">Category</th>
                    <th className="py-2 pl-2 text-right font-medium">Stock Units</th>
                    <th className="py-2 pl-2 text-right font-medium">Cost Value</th>
                    <th className="py-2 pl-2 text-right font-medium">90d Units</th>
                    <th className="py-2 pl-2 text-right font-medium">Days of Supply</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E2E7E4]">
                  {data.slow_movers.map((s) => (
                    <tr key={s.product_id} className="hover:bg-[#F6F7F6]">
                      <td className="font-mono-data py-2 pr-2 text-[#5C6B63]">
                        #{s.product_id}
                      </td>
                      <td className="py-2 pr-2 font-medium text-[#111A16]">
                        {s.product_name}
                      </td>
                      <td className="py-2 pr-2 text-[#46544D]">{s.category}</td>
                      <td className="tabular py-2 pl-2 text-right text-[#46544D]">
                        {formatInt(s.total_stoc)}
                      </td>
                      <td className="tabular py-2 pl-2 text-right text-[#111A16]">
                        {formatRon(s.inv_cost_ron, 2)} RON
                      </td>
                      <td className="tabular py-2 pl-2 text-right text-[#46544D]">
                        {formatInt(s.qty_90d)}
                      </td>
                      <td className="tabular py-2 pl-2 text-right font-medium text-[#B54708]">
                        {s.days_of_supply !== null ? `${s.days_of_supply.toFixed(1)} d` : "∞ (0 sold)"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
