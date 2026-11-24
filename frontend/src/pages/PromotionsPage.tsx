import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { usePromotions } from "../api/client";
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
  formatSignedPct,
} from "../utils/format";

export function PromotionsPage() {
  const { filters } = useFilters();
  const { data, isLoading, isPlaceholderData, isError, error, refetch } =
    usePromotions(filters);

  if (isError && !data) {
    return (
      <PanelError
        title="Unable to load Promotions & Margin Lab"
        message={error instanceof Error ? error.message : "Request failed"}
        onRetry={() => void refetch()}
      />
    );
  }

  const sum = data?.summary;

  return (
    <div
      className={`space-y-5 transition-opacity duration-150 ${
        isPlaceholderData ? "opacity-60" : "opacity-100"
      }`}
    >
      {isLoading || !sum ? (
        <KpiStripSkeleton count={5} />
      ) : (
        <section className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <KpiCard
            label="Active Campaigns"
            value={formatInt(sum.active_campaigns)}
            subtext="Excludes test records"
          />
          <KpiCard
            label="Promo Revenue"
            value={formatCompactRon(sum.promo_revenue_ron)}
            unit="RON"
            delta={`${formatPct(sum.promo_rev_share_pct, 1)} of net sales`}
            tone="neutral"
          />
          <KpiCard
            label="Discounts Granted"
            value={formatCompactRon(sum.total_discount_ron)}
            unit="RON"
            subtext="Ex-VAT price reductions"
          />
          <KpiCard
            label="Promo Gross Profit"
            value={formatCompactRon(sum.promo_profit_ron)}
            unit="RON"
            delta={`${formatPct(sum.promo_margin_pct, 1)} margin`}
            tone={sum.promo_margin_pct < 18 ? "warning" : "positive"}
          />
          <KpiCard
            label="Below-Cost Sales (Qty > 0)"
            value={formatInt(sum.below_cost_lines)}
            unit="lines"
            delta={`${formatRon(sum.below_cost_loss_ron)} RON loss`}
            tone="danger"
            subtext="Excludes customer returns"
          />
        </section>
      )}

      {/* Uplift Comparison Chart */}
      {isLoading || !data ? (
        <ChartCardSkeleton heightClass="h-80" />
      ) : (
        <section className="rounded-lg border border-[#E2E7E4] bg-white p-5">
          <h2 className="text-balance text-sm font-semibold text-[#111A16]">
            Daily Revenue Uplift vs. Daily Profit Uplift (% vs. Prior 28 Days)
          </h2>
          <p className="mt-0.5 text-xs text-[#5C6B63]">
            Evaluates promo SKU run-rate during each campaign against the 28-day pre-campaign baseline
          </p>

          <div className="mt-4 h-80 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={data.campaigns}
                margin={{ top: 12, right: 16, left: 0, bottom: 28 }}
              >
                <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="#E2E7E4" />
                <XAxis
                  dataKey="nume"
                  tick={{ fill: "#5C6B63", fontSize: 10 }}
                  interval={0}
                  angle={-15}
                  textAnchor="end"
                  height={62}
                  axisLine={{ stroke: "#E2E7E4" }}
                  tickLine={false}
                />
                <YAxis
                  tickFormatter={(v: number) => `${v}%`}
                  tick={{ fill: "#5C6B63", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  width={48}
                />
                <Tooltip content={<ChartTooltip unitMode="pct" />} />
                <ReferenceLine y={0} stroke="#94A3B8" strokeWidth={1.5} />
                <Bar
                  dataKey="rev_uplift_pct"
                  name="Revenue Uplift %"
                  fill="#94A3B8"
                  radius={[2, 2, 0, 0]}
                  maxBarSize={22}
                />
                <Bar
                  dataKey="profit_uplift_pct"
                  name="Profit Uplift %"
                  radius={[2, 2, 0, 0]}
                  maxBarSize={22}
                >
                  {data.campaigns.map((c) => (
                    <Cell
                      key={c.id}
                      fill={
                        c.verdict === "net_loss"
                          ? "#B42318"
                          : c.verdict === "margin_eroding"
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

      {/* YoY Over-Discounting Comparison */}
      {data && data.yoy_comparisons.length > 0 && (
        <section className="space-y-3">
          {data.yoy_comparisons.map((yoy) => (
            <div
              key={yoy.label}
              className="rounded-lg border border-[#E2E7E4] bg-white p-5"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <div>
                  <h2 className="text-balance text-sm font-semibold text-[#111A16]">
                    Year-over-Year Discount Depth Experiment: {yoy.label}
                  </h2>
                  <p className="mt-0.5 text-xs text-[#5C6B63]">
                    Same {yoy.campaign_2025.sku_count} sunscreen SKUs · deepening discount from -15% to -20% eroded gross profit
                  </p>
                </div>
                <span className="tabular text-xs font-semibold text-[#B42318]">
                  {formatRon(yoy.profit_delta_ron)} RON profit · {yoy.margin_delta_pp.toFixed(1)} pp margin
                </span>
              </div>

              <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
                {[yoy.campaign_2025, yoy.campaign_2026].map((c, idx) => (
                  <div
                    key={c.id}
                    className={`rounded-md border p-4 ${
                      idx === 1
                        ? "border-[#FECDCA] bg-[#FEF3F2]/50"
                        : "border-[#E2E7E4] bg-[#F6F7F6]"
                    }`}
                  >
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="text-xs font-semibold text-[#111A16]">
                        {c.nume}
                      </span>
                      <span className="font-mono-data text-[11px] text-[#5C6B63]">
                        {c.inceput} – {c.sfarsit}
                      </span>
                    </div>
                    <div className="mt-3 grid grid-cols-4 gap-2 text-xs">
                      <div>
                        <div className="text-[#5C6B63]">Revenue</div>
                        <div className="tabular mt-0.5 font-semibold text-[#111A16]">
                          {formatRon(c.revenue_ron)}
                        </div>
                      </div>
                      <div>
                        <div className="text-[#5C6B63]">Discounts</div>
                        <div className="tabular mt-0.5 font-semibold text-[#111A16]">
                          {formatRon(c.discount_ron)}
                        </div>
                      </div>
                      <div>
                        <div className="text-[#5C6B63]">Profit</div>
                        <div
                          className={`tabular mt-0.5 font-semibold ${
                            idx === 1 ? "text-[#B42318]" : "text-[#146C43]"
                          }`}
                        >
                          {formatRon(c.profit_ron)}
                        </div>
                      </div>
                      <div>
                        <div className="text-[#5C6B63]">Margin</div>
                        <div
                          className={`tabular mt-0.5 font-semibold ${
                            idx === 1 ? "text-[#B42318]" : "text-[#146C43]"
                          }`}
                        >
                          {formatPct(c.margin_pct, 1)}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </section>
      )}

      {/* Campaign Scorecard Table */}
      {isLoading || !data ? (
        <TableCardSkeleton rows={10} />
      ) : (
        <section className="rounded-lg border border-[#E2E7E4] bg-white p-5">
          <h2 className="text-balance text-sm font-semibold text-[#111A16]">
            Campaign Margin Scorecard (RON fără TVA)
          </h2>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full border-collapse text-left text-xs">
              <thead className="border-b border-[#E2E7E4] text-[#5C6B63]">
                <tr>
                  <th className="py-2 pr-2 font-medium">Campaign</th>
                  <th className="py-2 pr-2 font-medium">Mechanic</th>
                  <th className="py-2 pr-2 font-medium">Window</th>
                  <th className="py-2 pl-2 text-right font-medium">Revenue</th>
                  <th className="py-2 pl-2 text-right font-medium">Discounts</th>
                  <th className="py-2 pl-2 text-right font-medium">Profit</th>
                  <th className="py-2 pl-2 text-right font-medium">Margin</th>
                  <th className="py-2 pl-2 text-right font-medium">Below-Cost</th>
                  <th className="py-2 pl-2 text-right font-medium">Profit Uplift</th>
                  <th className="py-2 pl-3 font-medium">Verdict</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E2E7E4]">
                {data.campaigns.map((c) => (
                  <tr key={c.id} className="hover:bg-[#F6F7F6]">
                    <td className="py-2.5 pr-2 font-medium text-[#111A16]">
                      {c.nume}
                    </td>
                    <td className="py-2.5 pr-2 text-[#46544D]">
                      {c.tip === "2+1"
                        ? "2+1"
                        : c.tip === "procent"
                          ? `-${c.valoare}%`
                          : `-${c.valoare} lei`}
                    </td>
                    <td className="font-mono-data py-2.5 pr-2 text-[#5C6B63]">
                      {c.inceput}..{c.sfarsit.slice(5)}
                    </td>
                    <td className="tabular py-2.5 pl-2 text-right text-[#111A16]">
                      {formatRon(c.revenue_ron)}
                    </td>
                    <td className="tabular py-2.5 pl-2 text-right text-[#46544D]">
                      {formatRon(c.discount_ron)}
                    </td>
                    <td
                      className={`tabular py-2.5 pl-2 text-right font-medium ${
                        c.profit_ron < 0 ? "text-[#B42318]" : "text-[#111A16]"
                      }`}
                    >
                      {formatRon(c.profit_ron)}
                    </td>
                    <td
                      className={`tabular py-2.5 pl-2 text-right font-medium ${
                        c.margin_pct < 0
                          ? "text-[#B42318]"
                          : c.margin_pct < 15
                            ? "text-[#B54708]"
                            : "text-[#146C43]"
                      }`}
                    >
                      {formatPct(c.margin_pct, 1)}
                    </td>
                    <td className="tabular py-2.5 pl-2 text-right text-[#46544D]">
                      {c.below_cost_lines > 0 ? (
                        <span className="text-[#B42318]">
                          {formatInt(c.below_cost_lines)} ({formatRon(c.below_cost_loss_ron)})
                        </span>
                      ) : (
                        "0"
                      )}
                    </td>
                    <td
                      className={`tabular py-2.5 pl-2 text-right ${
                        c.profit_uplift_pct < 0 ? "text-[#B42318]" : "text-[#146C43]"
                      }`}
                    >
                      {formatSignedPct(c.profit_uplift_pct, 1)}
                    </td>
                    <td className="py-2.5 pl-3">
                      {c.verdict === "net_loss" && (
                        <span className="rounded bg-[#FEF3F2] px-2 py-0.5 text-[11px] font-medium text-[#B42318]">
                          Net Loss
                        </span>
                      )}
                      {c.verdict === "margin_eroding" && (
                        <span className="rounded bg-[#FFFAEB] px-2 py-0.5 text-[11px] font-medium text-[#B54708]">
                          Margin Eroding
                        </span>
                      )}
                      {c.verdict === "profitable" && (
                        <span className="rounded bg-[#ECF6F0] px-2 py-0.5 text-[11px] font-medium text-[#146C43]">
                          Profitable
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {data.excluded_test_promos.length > 0 && (
            <div className="mt-4 border-t border-[#E2E7E4] pt-3 text-xs text-[#5C6B63]">
              Data hygiene exclusion:{" "}
              {data.excluded_test_promos.map((tp) => (
                <span key={tp.id} className="font-mono-data">
                  ID {tp.id} ({tp.nume}, {tp.inceput}..{tp.sfarsit}, {tp.reason})
                </span>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
