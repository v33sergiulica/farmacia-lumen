import { X } from "lucide-react";
import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useStores, useStoreTrend } from "../api/client";
import { ChartTooltip } from "../components/ChartTooltip";
import { PanelError } from "../components/PanelError";
import { ChartCardSkeleton, TableCardSkeleton } from "../components/Skeletons";
import { useFilters } from "../context/FilterContext";
import {
  formatAxisRon,
  formatCompactRon,
  formatInt,
  formatPct,
  formatRon,
  shortStoreName,
} from "../utils/format";

type SortKey =
  | "attainment_pct"
  | "revenue_ron"
  | "rev_per_active_month"
  | "rev_per_sqm_month"
  | "margin_pct";

export function StoresPage() {
  const { filters } = useFilters();
  const [sortBy, setSortBy] = useState<SortKey>("attainment_pct");
  const [metricView, setMetricView] = useState<"total" | "normalized">("total");
  const [selectedStoreId, setSelectedStoreId] = useState<number | null>(filters.store_id);
  const [trendGranularity, setTrendGranularity] = useState<"month" | "week">("month");

  useEffect(() => {
    if (filters.store_id !== null) {
      setSelectedStoreId(filters.store_id);
    }
  }, [filters.store_id]);

  const { data, isLoading, isPlaceholderData, isError, error, refetch } = useStores(
    filters,
    sortBy,
  );
  const trendQuery = useStoreTrend(selectedStoreId, filters, trendGranularity);

  if (isError && !data) {
    return (
      <PanelError
        title="Unable to load Store Performance"
        message={error instanceof Error ? error.message : "Request failed"}
        onRetry={() => void refetch()}
      />
    );
  }

  // Merge sibling series into chart rows if present
  const drillData = trendQuery.data;
  const combinedSeries = drillData
    ? drillData.series.map((pt, idx) => ({
        ...pt,
        sibling_rev: drillData.sibling_comparison?.series[idx]?.revenue_ron ?? null,
      }))
    : [];
  const hasDrillTargets =
    trendGranularity === "month" &&
    combinedSeries.some((pt) => pt.target_ron !== null);

  return (
    <div
      className={`space-y-5 transition-opacity duration-150 ${
        isPlaceholderData ? "opacity-60" : "opacity-100"
      }`}
    >
      {data && !data.target_available && (
        <div className="rounded-lg border border-[#FEDF89] bg-[#FFFAEB] px-4 py-2.5 text-xs text-[#B54708]">
          Store targets (<span className="font-mono-data">target_lunar</span>) are unavailable under category filters. Clear Category to inspect target attainment.
        </div>
      )}

      {/* Regional Attainment Anchor */}
      {isLoading || !data ? (
        <ChartCardSkeleton heightClass="h-72" />
      ) : (
        <section className="rounded-lg border border-[#E2E7E4] bg-white p-5">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <div>
              <h2 className="text-balance text-sm font-semibold text-[#111A16]">
                {data.target_available
                  ? "Regional Target Attainment (% vs. Target)"
                  : "Regional Net Revenue (RON fără TVA)"}
              </h2>
              <p className="mt-0.5 text-xs text-[#5C6B63]">
                {data.target_available && data.chain_avg_attainment_pct !== null
                  ? `Chain average: ${data.chain_avg_attainment_pct.toFixed(2)}% (excluding <80% outliers: ${data.chain_avg_excl_outliers_pct?.toFixed(2)}%)`
                  : "Click any pharmacy below to inspect its monthly trajectory and events"}
              </p>
            </div>
          </div>

          <div className="mt-4 h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={data.regions}
                layout="vertical"
                margin={{ top: 4, right: 24, left: 10, bottom: 4 }}
              >
                <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="#E2E7E4" />
                <XAxis
                  type="number"
                  domain={data.target_available ? [0, 105] : [0, "auto"]}
                  tickFormatter={(v: number) =>
                    data.target_available ? `${v}%` : formatAxisRon(v)
                  }
                  tick={{ fill: "#5C6B63", fontSize: 11 }}
                  axisLine={{ stroke: "#E2E7E4" }}
                  tickLine={false}
                />
                <YAxis
                  type="category"
                  dataKey="nume"
                  width={140}
                  tick={{ fill: "#111A16", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  content={
                    <ChartTooltip unitMode={data.target_available ? "pct" : "ron"} />
                  }
                />
                {data.target_available && (
                  <ReferenceLine
                    x={100}
                    stroke="#94A3B8"
                    strokeDasharray="4 4"
                    label={{ value: "100%", position: "top", fill: "#5C6B63", fontSize: 10 }}
                  />
                )}
                <Bar
                  dataKey={data.target_available ? "attainment_pct" : "revenue_ron"}
                  name={data.target_available ? "Attainment %" : "Net Revenue"}
                  radius={[0, 3, 3, 0]}
                  barSize={18}
                >
                  {data.regions.map((reg) => {
                    const isLow =
                      data.target_available &&
                      reg.attainment_pct !== null &&
                      reg.attainment_pct < 90;
                    return (
                      <Cell
                        key={reg.id}
                        fill={isLow ? "#B42318" : "#146C43"}
                      />
                    );
                  })}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      {/* 21-Pharmacy Leaderboard */}
      {isLoading || !data ? (
        <TableCardSkeleton rows={10} />
      ) : (
        <section className="rounded-lg border border-[#E2E7E4] bg-white p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-balance text-sm font-semibold text-[#111A16]">
                Pharmacy Leaderboard ({data.stores.length})
              </h2>
              <p className="mt-0.5 text-xs text-[#5C6B63]">
                Select any row to open trajectory, sibling city benchmark, and transfer history
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2.5">
              <div className="inline-flex rounded-lg border border-[#E2E7E4] bg-[#F6F7F6] p-1">
                {(
                  [
                    { id: "total", label: "Total Period" },
                    { id: "normalized", label: "Normalized / Active Mo" },
                  ] as const
                ).map((mode) => (
                  <button
                    key={mode.id}
                    type="button"
                    onClick={() => setMetricView(mode.id)}
                    className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                      metricView === mode.id
                        ? "bg-white text-[#146C43] ring-1 ring-[#E2E7E4]"
                        : "text-[#46544D] hover:text-[#111A16]"
                    }`}
                  >
                    {mode.label}
                  </button>
                ))}
              </div>
              <select
                aria-label="Sort pharmacies"
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as SortKey)}
                className="h-8 rounded-md border border-[#E2E7E4] bg-white px-2.5 text-xs text-[#111A16] focus:border-[#146C43] focus:outline-none"
              >
                <option value="attainment_pct">Sort: Attainment % (lowest first)</option>
                <option value="revenue_ron">Sort: Total Revenue</option>
                <option value="rev_per_active_month">Sort: Rev / Active Month</option>
                <option value="rev_per_sqm_month">Sort: Rev / sqm / Month</option>
                <option value="margin_pct">Sort: Margin %</option>
              </select>
            </div>
          </div>

          <div className="mt-4 overflow-x-auto">
            <table className="w-full border-collapse text-left text-xs">
              <thead className="border-b border-[#E2E7E4] text-[#5C6B63]">
                <tr>
                  <th className="py-2 pr-2 font-medium">ID</th>
                  <th className="py-2 pr-2 font-medium">Pharmacy</th>
                  <th className="py-2 pr-2 font-medium">Region</th>
                  <th className="py-2 pr-2 font-medium">Lifecycle &amp; Flags</th>
                  <th className="py-2 pl-2 text-right font-medium">Mo</th>
                  {metricView === "total" ? (
                    <>
                      <th className="py-2 pl-2 text-right font-medium">Revenue (RON)</th>
                      <th className="py-2 pl-2 text-right font-medium">Target</th>
                      <th className="py-2 pl-2 text-right font-medium">Attainment</th>
                      <th className="py-2 pl-2 text-right font-medium">Variance</th>
                    </>
                  ) : (
                    <>
                      <th className="py-2 pl-2 text-right font-medium">Rev / Active Mo</th>
                      <th className="py-2 pl-2 text-right font-medium">Rev / sqm / Mo</th>
                      <th className="py-2 pl-2 text-right font-medium">Rev / Emp / Mo</th>
                      <th className="py-2 pl-2 text-right font-medium">AOV (RON)</th>
                    </>
                  )}
                  <th className="py-2 pl-2 text-right font-medium">Margin</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E2E7E4]">
                {data.stores.map((s) => {
                  const isCrit = s.attainment_pct !== null && s.attainment_pct < 82;
                  const hasOutage = s.anomaly_flags.includes("outage_month");
                  return (
                    <tr
                      key={s.id}
                      onClick={() => setSelectedStoreId(s.id)}
                      className={`cursor-pointer transition-colors hover:bg-[#ECF6F0]/60 ${
                        selectedStoreId === s.id ? "bg-[#ECF6F0]" : ""
                      }`}
                    >
                      <td className="font-mono-data py-2.5 pr-2 text-[#5C6B63]">
                        #{s.id}
                      </td>
                      <td className="py-2.5 pr-2 font-medium text-[#111A16]">
                        {shortStoreName(s.nume)}
                      </td>
                      <td className="py-2.5 pr-2 text-[#46544D]">{s.regiune}</td>
                      <td className="py-2.5 pr-2">
                        <div className="flex flex-wrap gap-1">
                          {s.status === "closed" && (
                            <span className="font-mono-data rounded bg-[#F6F7F6] px-1.5 py-0.5 text-[11px] text-[#46544D] ring-1 ring-[#E2E7E4]">
                              Closed {s.inchis_la}
                            </span>
                          )}
                          {s.status === "opened_mid_period" && (
                            <span className="font-mono-data rounded bg-[#ECF6F0] px-1.5 py-0.5 text-[11px] text-[#146C43] ring-1 ring-[#B7DFC9]">
                              Opened {s.deschis_la}
                            </span>
                          )}
                          {isCrit && (
                            <span className="rounded bg-[#FEF3F2] px-1.5 py-0.5 text-[11px] font-medium text-[#B42318]">
                              Underperforming
                            </span>
                          )}
                          {hasOutage && (
                            <span className="rounded bg-[#FFFAEB] px-1.5 py-0.5 text-[11px] font-medium text-[#B54708]">
                              Outage month
                            </span>
                          )}
                          {!isCrit && !hasOutage && s.status === "active" && (
                            <span className="text-[#5C6B63]">Active</span>
                          )}
                        </div>
                      </td>
                      <td className="tabular py-2.5 pl-2 text-right text-[#46544D]">
                        {s.active_months}
                      </td>
                      {metricView === "total" ? (
                        <>
                          <td className="tabular py-2.5 pl-2 text-right font-medium text-[#111A16]">
                            {formatRon(s.revenue_ron)}
                          </td>
                          <td className="tabular py-2.5 pl-2 text-right text-[#5C6B63]">
                            {s.target_ron !== null ? formatRon(s.target_ron) : "—"}
                          </td>
                          <td
                            className={`tabular py-2.5 pl-2 text-right font-semibold ${
                              isCrit
                                ? "text-[#B42318]"
                                : s.attainment_pct !== null && s.attainment_pct < 93
                                  ? "text-[#B54708]"
                                  : "text-[#146C43]"
                            }`}
                          >
                            {s.attainment_pct !== null
                              ? formatPct(s.attainment_pct, 1)
                              : "—"}
                          </td>
                          <td
                            className={`tabular py-2.5 pl-2 text-right ${
                              s.variance_ron !== null && s.variance_ron < 0
                                ? "text-[#B42318]"
                                : "text-[#146C43]"
                            }`}
                          >
                            {s.variance_ron !== null
                              ? formatCompactRon(s.variance_ron)
                              : "—"}
                          </td>
                        </>
                      ) : (
                        <>
                          <td className="tabular py-2.5 pl-2 text-right font-medium text-[#111A16]">
                            {formatRon(s.rev_per_active_month)}
                          </td>
                          <td className="tabular py-2.5 pl-2 text-right text-[#46544D]">
                            {formatRon(s.rev_per_sqm_month)}
                          </td>
                          <td className="tabular py-2.5 pl-2 text-right text-[#46544D]">
                            {formatRon(s.rev_per_emp_month)}
                          </td>
                          <td className="tabular py-2.5 pl-2 text-right text-[#46544D]">
                            {formatRon(s.aov_ron, 2)}
                          </td>
                        </>
                      )}
                      <td className="tabular py-2.5 pl-2 text-right text-[#46544D]">
                        {formatPct(s.margin_pct, 1)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Store Drilldown Slide-Over Drawer */}
      {selectedStoreId !== null && (
        <div className="fixed inset-0 z-40 flex justify-end">
          <div
            className="fixed inset-0 bg-[#111A16]/20"
            onClick={() => setSelectedStoreId(null)}
            aria-hidden="true"
          />
          <aside className="relative z-10 flex h-full w-full max-w-2xl flex-col border-l border-[#E2E7E4] bg-white">
            <div className="flex items-center justify-between border-b border-[#E2E7E4] px-5 py-4">
              <div>
                <h3 className="text-base font-semibold text-[#111A16]">
                  {drillData
                    ? `#${drillData.store.id} ${drillData.store.nume}`
                    : `Store #${selectedStoreId} Trajectory`}
                </h3>
                {drillData && (
                  <p className="mt-0.5 text-xs text-[#5C6B63]">
                    {drillData.store.regiune} · {drillData.store.sqm} sqm ·{" "}
                    {drillData.store.employees} staff · Opened {drillData.store.deschis_la}
                    {drillData.store.inchis_la ? ` · Closed ${drillData.store.inchis_la}` : ""}
                  </p>
                )}
              </div>
              <button
                type="button"
                onClick={() => setSelectedStoreId(null)}
                aria-label="Close store drawer"
                className="rounded-md p-1.5 text-[#5C6B63] hover:bg-[#F6F7F6]"
              >
                <X size={18} strokeWidth={1.5} />
              </button>
            </div>

            <div className="flex-1 space-y-5 overflow-y-auto p-5">
              {trendQuery.isLoading || !drillData ? (
                <ChartCardSkeleton heightClass="h-64" />
              ) : (
                <>
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <div className="text-xs font-medium text-[#111A16]">
                        Store Trajectory{hasDrillTargets ? " vs. Target" : ""}
                        {drillData.sibling_comparison
                          ? ` & ${shortStoreName(drillData.sibling_comparison.store_name)}`
                          : ""}{" "}
                        (RON fără TVA)
                      </div>
                      <div className="mt-1.5 flex flex-wrap items-center gap-4 text-[11px] text-[#46544D]">
                        <span className="inline-flex items-center gap-1.5">
                          <span className="inline-block h-2.5 w-2.5 rounded-xs bg-[#146C43]" />
                          {shortStoreName(drillData.store.nume)}
                        </span>
                        {hasDrillTargets && (
                          <span className="inline-flex items-center gap-1.5">
                            <span className="inline-block h-0.5 w-4 border-t-2 border-dashed border-[#94A3B8]" />
                            Target
                          </span>
                        )}
                        {drillData.sibling_comparison && (
                          <span className="inline-flex items-center gap-1.5">
                            <span className="inline-block h-0.5 w-4 bg-[#B54708]" />
                            {shortStoreName(drillData.sibling_comparison.store_name)}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="inline-flex rounded-lg border border-[#E2E7E4] bg-[#F6F7F6] p-1">
                      {(["month", "week"] as const).map((g) => (
                        <button
                          key={g}
                          type="button"
                          onClick={() => setTrendGranularity(g)}
                          className={`rounded px-2 py-0.5 text-xs font-medium ${
                            trendGranularity === g
                              ? "bg-white text-[#146C43] ring-1 ring-[#E2E7E4]"
                              : "text-[#46544D]"
                          }`}
                        >
                          {g === "month" ? "Monthly" : "Weekly"}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="h-64 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <ComposedChart
                        data={combinedSeries}
                        margin={{ top: 10, right: 12, left: 0, bottom: 4 }}
                      >
                        <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="#E2E7E4" />
                        <XAxis
                          dataKey="period"
                          tick={{ fill: "#5C6B63", fontSize: 11 }}
                          axisLine={{ stroke: "#E2E7E4" }}
                          tickLine={false}
                        />
                        <YAxis
                          tickFormatter={formatAxisRon}
                          tick={{ fill: "#5C6B63", fontSize: 11 }}
                          axisLine={false}
                          tickLine={false}
                          width={50}
                        />
                        <Tooltip content={<ChartTooltip />} />
                        <Bar
                          dataKey="revenue_ron"
                          name={shortStoreName(drillData.store.nume)}
                          fill="#146C43"
                          radius={[3, 3, 0, 0]}
                          maxBarSize={28}
                        />
                        {trendGranularity === "month" && (
                          <Line
                            type="monotone"
                            dataKey="target_ron"
                            name="Target"
                            stroke="#94A3B8"
                            strokeWidth={2}
                            strokeDasharray="5 4"
                            dot={false}
                          />
                        )}
                        {drillData.sibling_comparison && (
                          <Line
                            type="monotone"
                            dataKey="sibling_rev"
                            name={shortStoreName(drillData.sibling_comparison.store_name)}
                            stroke="#B54708"
                            strokeWidth={1.75}
                            dot={false}
                          />
                        )}
                      </ComposedChart>
                    </ResponsiveContainer>
                  </div>

                  {drillData.events.length > 0 && (
                    <div>
                      <h4 className="text-xs font-semibold uppercase tracking-wide text-[#5C6B63]">
                        Detected Operational Events
                      </h4>
                      <div className="mt-2 space-y-2">
                        {drillData.events.map((ev, i) => (
                          <div
                            key={i}
                            className="rounded-md border border-[#E2E7E4] bg-[#F6F7F6] p-3 text-xs"
                          >
                            <div className="flex items-center justify-between gap-2">
                              <span className="font-semibold text-[#111A16]">
                                {ev.title}
                              </span>
                              <span className="font-mono-data text-[#5C6B63]">
                                {ev.date}
                              </span>
                            </div>
                            <p className="mt-1 text-[#46544D]">{ev.impact_summary}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {drillData.transfers.length > 0 && (
                    <div>
                      <h4 className="text-xs font-semibold uppercase tracking-wide text-[#5C6B63]">
                        Closure / Reallocation Stock Transfers
                      </h4>
                      <table className="mt-2 w-full border-collapse text-left text-xs">
                        <thead className="border-b border-[#E2E7E4] text-[#5C6B63]">
                          <tr>
                            <th className="py-1.5 font-medium">Pharmacy</th>
                            <th className="py-1.5 text-right font-medium">SKUs</th>
                            <th className="py-1.5 text-right font-medium">Net Units</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[#E2E7E4]">
                          {drillData.transfers.map((tr) => (
                            <tr key={tr.store_id}>
                              <td className="py-1.5 text-[#111A16]">
                                #{tr.store_id} {shortStoreName(tr.store_name)}
                              </td>
                              <td className="tabular py-1.5 text-right text-[#46544D]">
                                {formatInt(tr.skus)}
                              </td>
                              <td
                                className={`tabular py-1.5 text-right font-medium ${
                                  tr.units < 0 ? "text-[#B42318]" : "text-[#146C43]"
                                }`}
                              >
                                {tr.units > 0 ? `+${tr.units}` : tr.units}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </>
              )}
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}
