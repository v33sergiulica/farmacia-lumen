import { useState } from "react";
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  BarChart,
} from "recharts";
import { useOverview } from "../api/client";
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
  formatAxisRon,
  formatCompactRon,
  formatInt,
  formatPct,
  formatRon,
  formatSignedPct,
} from "../utils/format";

export function OverviewPage() {
  const { filters } = useFilters();
  const [granularity, setGranularity] = useState<"month" | "week">("month");
  const [skuTab, setSkuTab] = useState<"top" | "bottom">("top");

  const { data, isLoading, isPlaceholderData, isError, error, refetch } =
    useOverview(filters, granularity);

  if (isError && !data) {
    return (
      <PanelError
        title="Unable to load Executive Overview"
        message={error instanceof Error ? error.message : "Request failed"}
        onRetry={() => void refetch()}
      />
    );
  }

  const kpis = data?.kpis;
  const attTone =
    kpis?.attainment_pct === null || kpis?.attainment_pct === undefined
      ? "neutral"
      : kpis.attainment_pct >= 98
        ? "positive"
        : kpis.attainment_pct >= 92
          ? "warning"
          : "danger";

  const skuRows = data
    ? skuTab === "top"
      ? data.top_products
      : data.bottom_products
    : [];

  return (
    <div
      className={`space-y-5 transition-opacity duration-150 ${
        isPlaceholderData ? "opacity-60" : "opacity-100"
      }`}
    >
      {isError && (
        <PanelError
          message={error instanceof Error ? error.message : "Refresh failed"}
          onRetry={() => void refetch()}
        />
      )}

      {/* Target availability notice when filtered by category */}
      {kpis && !kpis.target_available && (
        <div className="rounded-lg border border-[#FEDF89] bg-[#FFFAEB] px-4 py-2.5 text-xs text-[#B54708]">
          Store-level monthly targets (<span className="font-mono-data">target_lunar</span>) are not defined per category. Clear the Category filter to view target attainment.
        </div>
      )}

      {/* Headline KPI Strip */}
      {isLoading || !kpis ? (
        <KpiStripSkeleton count={6} />
      ) : (
        <section className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          <KpiCard
            label="Net Revenue"
            value={formatCompactRon(kpis.net_revenue_ron)}
            unit="RON"
            delta={
              kpis.rev_vs_prev_period_pct !== null
                ? `${formatSignedPct(kpis.rev_vs_prev_period_pct)} vs prior`
                : undefined
            }
            tone={
              kpis.rev_vs_prev_period_pct !== null && kpis.rev_vs_prev_period_pct >= 0
                ? "positive"
                : "neutral"
            }
            subtext={`${formatRon(kpis.net_revenue_ron)} ex-VAT`}
          />
          <KpiCard
            label="Target Attainment"
            value={
              kpis.target_available && kpis.attainment_pct !== null
                ? formatPct(kpis.attainment_pct, 2)
                : "N/A"
            }
            delta={
              kpis.target_available && kpis.variance_ron !== null
                ? `${formatCompactRon(kpis.variance_ron)} RON`
                : "Category slice"
            }
            tone={attTone}
            subtext={
              kpis.target_available && kpis.target_ron !== null
                ? `Target ${formatCompactRon(kpis.target_ron)}`
                : "Store-level only"
            }
          />
          <KpiCard
            label="Gross Profit"
            value={formatCompactRon(kpis.gross_profit_ron)}
            unit="RON"
            delta={`${formatPct(kpis.margin_pct, 2)} margin`}
            tone="positive"
            subtext={`Discounts ${formatCompactRon(kpis.discount_ron)}`}
          />
          <KpiCard
            label="Receipts & AOV"
            value={formatInt(kpis.receipts)}
            delta={`${formatRon(kpis.aov_ron, 2)} RON AOV`}
            tone="neutral"
            subtext="Ex-VAT basket avg"
          />
          <KpiCard
            label="Net Units Sold"
            value={formatInt(kpis.units_net)}
            subtext={`Gross sales ${formatCompactRon(kpis.gross_revenue_ron)}`}
          />
          <KpiCard
            label="Return Rate"
            value={formatPct(kpis.return_rate_units_pct, 2)}
            delta={`${formatInt(kpis.return_lines)} lines`}
            tone={kpis.return_rate_units_pct > 1.0 ? "warning" : "neutral"}
            subtext={`-${formatRon(kpis.return_value_ron)} RON`}
          />
        </section>
      )}

      {/* Primary Visual Anchor: Revenue vs Target Trend */}
      {isLoading || !data ? (
        <ChartCardSkeleton heightClass="h-80" />
      ) : (
        <section className="rounded-lg border border-[#E2E7E4] bg-white p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-balance text-sm font-semibold text-[#111A16]">
                {granularity === "month" ? "Monthly" : "Weekly"} Revenue vs. Target &amp; Margin (RON fără TVA)
              </h2>
              <p className="mt-0.5 text-xs text-[#5C6B63]">
                {data.price_wave
                  ? `Repricing wave in ${data.price_wave.month}: ${data.price_wave.repriced_skus}/${data.price_wave.total_skus} SKUs (+${data.price_wave.avg_price_chg_pct.toFixed(1)}% price vs +${data.price_wave.avg_cost_chg_pct.toFixed(1)}% cost)`
                  : "Net revenue ex-VAT plotted against monthly store targets"}
              </p>
            </div>
            <div className="inline-flex rounded-lg border border-[#E2E7E4] bg-[#F6F7F6] p-1">
              {(["month", "week"] as const).map((g) => (
                <button
                  key={g}
                  type="button"
                  onClick={() => setGranularity(g)}
                  className={`rounded px-2.5 py-1 text-xs font-medium capitalize transition-colors ${
                    granularity === g
                      ? "bg-white text-[#146C43] ring-1 ring-[#E2E7E4]"
                      : "text-[#46544D] hover:text-[#111A16]"
                  }`}
                >
                  {g === "month" ? "Monthly" : "Weekly"}
                </button>
              ))}
            </div>
          </div>

          <div className="mt-4 h-80 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart
                data={data.series}
                margin={{ top: 14, right: 12, left: 0, bottom: 4 }}
              >
                <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="#E2E7E4" />
                <XAxis
                  dataKey="period"
                  tick={{ fill: "#5C6B63", fontSize: 11 }}
                  axisLine={{ stroke: "#E2E7E4" }}
                  tickLine={false}
                />
                <YAxis
                  yAxisId="ron"
                  tickFormatter={formatAxisRon}
                  tick={{ fill: "#5C6B63", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  width={54}
                />
                <YAxis
                  yAxisId="pct"
                  orientation="right"
                  domain={[0, 45]}
                  tickFormatter={(v: number) => `${v}%`}
                  tick={{ fill: "#5C6B63", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  width={42}
                />
                <Tooltip content={<ChartTooltip />} />
                <Bar
                  yAxisId="ron"
                  dataKey="revenue_ron"
                  name="Net Revenue"
                  fill="#146C43"
                  radius={[3, 3, 0, 0]}
                  maxBarSize={36}
                />
                {granularity === "month" && data.kpis.target_available && (
                  <Line
                    yAxisId="ron"
                    type="monotone"
                    dataKey="target_ron"
                    name="Target"
                    stroke="#94A3B8"
                    strokeWidth={2}
                    strokeDasharray="5 4"
                    dot={false}
                  />
                )}
                <Line
                  yAxisId="pct"
                  type="monotone"
                  dataKey="margin_pct"
                  name="Margin %"
                  stroke="#B54708"
                  strokeWidth={1.75}
                  dot={false}
                />
                {granularity === "month" &&
                  data.annotations.map((ann) => (
                    <ReferenceLine
                      key={`${ann.period}-${ann.type}`}
                      yAxisId="ron"
                      x={ann.period}
                      stroke="#5C6B63"
                      strokeDasharray="2 2"
                      label={{
                        value: ann.label,
                        position: "top",
                        fill: "#46544D",
                        fontSize: 10,
                      }}
                    />
                  ))}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      {/* Lower Split: Category Mix + Top/Bottom SKUs */}
      <section className="grid grid-cols-1 gap-5 xl:grid-cols-12">
        {isLoading || !data ? (
          <>
            <div className="xl:col-span-5">
              <ChartCardSkeleton heightClass="h-72" />
            </div>
            <div className="xl:col-span-7">
              <TableCardSkeleton rows={8} />
            </div>
          </>
        ) : (
          <>
            <div className="rounded-lg border border-[#E2E7E4] bg-white p-5 xl:col-span-5">
              <h2 className="text-balance text-sm font-semibold text-[#111A16]">
                Category Mix by Net Revenue (RON fără TVA)
              </h2>
              <p className="mt-0.5 text-xs text-[#5C6B63]">
                6 L1 categories · share and gross margin
              </p>
              <div className="mt-4 h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={data.category_mix}
                    layout="vertical"
                    margin={{ top: 4, right: 16, left: 4, bottom: 4 }}
                  >
                    <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="#E2E7E4" />
                    <XAxis
                      type="number"
                      tickFormatter={formatAxisRon}
                      tick={{ fill: "#5C6B63", fontSize: 11 }}
                      axisLine={{ stroke: "#E2E7E4" }}
                      tickLine={false}
                    />
                    <YAxis
                      type="category"
                      dataKey="nume"
                      width={136}
                      tick={{ fill: "#111A16", fontSize: 11 }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip content={<ChartTooltip />} />
                    <Bar
                      dataKey="revenue_ron"
                      name="Net Revenue"
                      fill="#146C43"
                      radius={[0, 3, 3, 0]}
                      barSize={20}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="mt-3 space-y-1.5 border-t border-[#E2E7E4] pt-3 text-xs">
                {data.category_mix.map((c) => (
                  <div key={c.id} className="flex items-center justify-between">
                    <span className="text-[#46544D]">{c.nume}</span>
                    <span className="tabular text-[#111A16]">
                      {formatPct(c.share_pct, 1)} share ·{" "}
                      <span className="text-[#146C43]">{formatPct(c.margin_pct, 1)} margin</span>
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-lg border border-[#E2E7E4] bg-white p-5 xl:col-span-7">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-balance text-sm font-semibold text-[#111A16]">
                    {skuTab === "top" ? "Top 10" : "Bottom 10 Active"} Products by Revenue (RON fără TVA)
                  </h2>
                  <p className="mt-0.5 text-xs text-[#5C6B63]">
                    Includes net units and return rate
                  </p>
                </div>
                <div className="inline-flex rounded-lg border border-[#E2E7E4] bg-[#F6F7F6] p-1">
                  {(["top", "bottom"] as const).map((tab) => (
                    <button
                      key={tab}
                      type="button"
                      onClick={() => setSkuTab(tab)}
                      className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                        skuTab === tab
                          ? "bg-white text-[#146C43] ring-1 ring-[#E2E7E4]"
                          : "text-[#46544D] hover:text-[#111A16]"
                      }`}
                    >
                      {tab === "top" ? "Top 10" : "Bottom 10"}
                    </button>
                  ))}
                </div>
              </div>

              <div className="mt-4 overflow-x-auto">
                <table className="w-full border-collapse text-left text-xs">
                  <thead className="border-b border-[#E2E7E4] text-[#5C6B63]">
                    <tr>
                      <th className="py-2 pr-2 font-medium">SKU</th>
                      <th className="py-2 pr-2 font-medium">Product</th>
                      <th className="py-2 pr-2 font-medium">Category</th>
                      <th className="py-2 pl-2 text-right font-medium">Revenue</th>
                      <th className="py-2 pl-2 text-right font-medium">Margin</th>
                      <th className="py-2 pl-2 text-right font-medium">Units</th>
                      <th className="py-2 pl-2 text-right font-medium">Return</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E2E7E4]">
                    {skuRows.map((p) => (
                      <tr key={p.id} className="hover:bg-[#F6F7F6]">
                        <td className="font-mono-data py-2 pr-2 text-[#5C6B63]">
                          #{p.id}
                        </td>
                        <td className="py-2 pr-2 font-medium text-[#111A16]">
                          {p.nume}
                        </td>
                        <td className="py-2 pr-2 text-[#46544D]">{p.category}</td>
                        <td className="tabular py-2 pl-2 text-right font-medium text-[#111A16]">
                          {formatRon(p.revenue_ron)}
                        </td>
                        <td className="tabular py-2 pl-2 text-right text-[#146C43]">
                          {formatPct(p.margin_pct, 1)}
                        </td>
                        <td className="tabular py-2 pl-2 text-right text-[#46544D]">
                          {formatInt(p.units)}
                        </td>
                        <td className="tabular py-2 pl-2 text-right text-[#5C6B63]">
                          {formatPct(p.return_rate_pct, 2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
