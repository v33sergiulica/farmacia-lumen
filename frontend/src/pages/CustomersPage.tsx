import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useCustomers } from "../api/client";
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
} from "../utils/format";

export function CustomersPage() {
  const { filters } = useFilters();
  const { data, isLoading, isPlaceholderData, isError, error, refetch } =
    useCustomers(filters);

  if (isError && !data) {
    return (
      <PanelError
        title="Unable to load Customers & Loyalty"
        message={error instanceof Error ? error.message : "Request failed"}
        onRetry={() => void refetch()}
      />
    );
  }

  const pen = data?.penetration;
  const aovDelta = pen ? pen.card_aov_ron - pen.nocard_aov_ron : 0;

  return (
    <div
      className={`space-y-5 transition-opacity duration-150 ${
        isPlaceholderData ? "opacity-60" : "opacity-100"
      }`}
    >
      {isLoading || !data || !pen ? (
        <KpiStripSkeleton count={4} />
      ) : (
        <section className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <KpiCard
            label="Registered Loyalty Members"
            value={formatInt(data.total_registered_members)}
            subtext={`${formatInt(pen.card_receipts)} card receipts`}
          />
          <KpiCard
            label="Loyalty Penetration"
            value={formatPct(pen.card_receipt_share_pct, 1)}
            delta={`${formatPct(pen.card_rev_share_pct, 1)} of revenue`}
            tone="positive"
            subtext={`${formatCompactRon(pen.card_revenue_ron)} RON`}
          />
          <KpiCard
            label="Card vs. Non-Card AOV"
            value={formatRon(pen.card_aov_ron, 2)}
            unit="RON"
            delta={`+${aovDelta.toFixed(2)} RON vs no-card (${formatRon(pen.nocard_aov_ron, 2)})`}
            tone="warning"
            subtext={`Margin ${formatPct(pen.card_margin_pct, 2)} vs ${formatPct(pen.nocard_margin_pct, 2)}`}
          />
          <KpiCard
            label="Dormant & One-Time Members"
            value={formatInt(data.dormant_members)}
            delta={`${formatInt(data.one_time_members)} one-time visitors`}
            tone="warning"
            subtext={`${((100 * data.dormant_members) / Math.max(data.total_registered_members, 1)).toFixed(1)}% zero-visit rate`}
          />
        </section>
      )}

      {/* Card vs No-Card Monthly AOV Trend */}
      {isLoading || !data ? (
        <ChartCardSkeleton heightClass="h-72" />
      ) : (
        <section className="rounded-lg border border-[#E2E7E4] bg-white p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-balance text-sm font-semibold text-[#111A16]">
                Monthly Card vs. Non-Card Average Basket Value (RON fără TVA)
              </h2>
              <p className="mt-0.5 text-xs text-[#5C6B63]">
                Demonstrates flat basket-size parity between loyalty cardholders and walk-in shoppers across all months
              </p>
            </div>
            <div className="flex items-center gap-4 text-xs text-[#46544D]">
              <span className="inline-flex items-center gap-1.5">
                <span className="inline-block h-0.5 w-4 bg-[#146C43]" />
                Loyalty Card
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="inline-block h-0.5 w-4 border-t-2 border-dashed border-[#94A3B8]" />
                Non-Card
              </span>
            </div>
          </div>

          <div className="mt-4 h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={data.monthly_loyalty_trend}
                margin={{ top: 10, right: 16, left: 0, bottom: 4 }}
              >
                <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="#E2E7E4" />
                <XAxis
                  dataKey="period"
                  tick={{ fill: "#5C6B63", fontSize: 11 }}
                  axisLine={{ stroke: "#E2E7E4" }}
                  tickLine={false}
                />
                <YAxis
                  domain={["auto", "auto"]}
                  tick={{ fill: "#5C6B63", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  width={44}
                />
                <Tooltip content={<ChartTooltip decimals={2} />} />
                <Line
                  type="monotone"
                  dataKey="card_aov_ron"
                  name="Loyalty Card AOV"
                  stroke="#146C43"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="nocard_aov_ron"
                  name="Non-Card AOV"
                  stroke="#94A3B8"
                  strokeWidth={2}
                  strokeDasharray="4 4"
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      {/* Frequency Distribution + Demographics */}
      <section className="grid grid-cols-1 gap-5 xl:grid-cols-12">
        {isLoading || !data ? (
          <>
            <div className="xl:col-span-6">
              <ChartCardSkeleton heightClass="h-72" />
            </div>
            <div className="xl:col-span-6">
              <TableCardSkeleton rows={8} />
            </div>
          </>
        ) : (
          <>
            <div className="rounded-lg border border-[#E2E7E4] bg-white p-5 xl:col-span-6">
              <h2 className="text-balance text-sm font-semibold text-[#111A16]">
                Loyalty Member Visit Frequency Distribution
              </h2>
              <p className="mt-0.5 text-xs text-[#5C6B63]">
                Amber highlights dormant (0 visits) and single-visit cohorts
              </p>

              <div className="mt-4 h-60 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={data.frequency_segments}
                    margin={{ top: 8, right: 12, left: 0, bottom: 4 }}
                  >
                    <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="#E2E7E4" />
                    <XAxis
                      dataKey="bucket"
                      tick={{ fill: "#5C6B63", fontSize: 10 }}
                      axisLine={{ stroke: "#E2E7E4" }}
                      tickLine={false}
                    />
                    <YAxis
                      tick={{ fill: "#5C6B63", fontSize: 11 }}
                      axisLine={false}
                      tickLine={false}
                      width={46}
                    />
                    <Tooltip content={<ChartTooltip unitMode="mixed" />} />
                    <Bar
                      dataKey="members"
                      name="Members"
                      radius={[3, 3, 0, 0]}
                      maxBarSize={40}
                    >
                      {data.frequency_segments.map((seg, idx) => (
                        <Cell
                          key={seg.bucket}
                          fill={idx <= 1 ? "#B54708" : "#146C43"}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>

              <div className="mt-3 overflow-x-auto border-t border-[#E2E7E4] pt-3">
                <table className="w-full border-collapse text-left text-xs">
                  <thead className="text-[#5C6B63]">
                    <tr>
                      <th className="py-1 font-medium">Segment</th>
                      <th className="py-1 text-right font-medium">Members</th>
                      <th className="py-1 text-right font-medium">Share</th>
                      <th className="py-1 text-right font-medium">Revenue</th>
                      <th className="py-1 text-right font-medium">Avg Spend</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E2E7E4]">
                    {data.frequency_segments.map((seg) => (
                      <tr key={seg.bucket}>
                        <td className="py-1.5 text-[#111A16]">{seg.bucket}</td>
                        <td className="tabular py-1.5 text-right text-[#46544D]">
                          {formatInt(seg.members)}
                        </td>
                        <td className="tabular py-1.5 text-right text-[#5C6B63]">
                          {formatPct(seg.share_pct, 1)}
                        </td>
                        <td className="tabular py-1.5 text-right font-medium text-[#111A16]">
                          {formatRon(seg.revenue_ron)}
                        </td>
                        <td className="tabular py-1.5 text-right text-[#46544D]">
                          {formatRon(seg.avg_spend_ron, 2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="rounded-lg border border-[#E2E7E4] bg-white p-5 xl:col-span-6">
              <h2 className="text-balance text-sm font-semibold text-[#111A16]">
                Active Cardholder Demographics (RON fără TVA)
              </h2>
              <p className="mt-0.5 text-xs text-[#5C6B63]">
                Revenue &amp; spend per active member by age band and gender
              </p>

              <div className="mt-4 h-52 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={data.demographics.by_age_band}
                    margin={{ top: 8, right: 12, left: 0, bottom: 4 }}
                  >
                    <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="#E2E7E4" />
                    <XAxis
                      dataKey="label"
                      tick={{ fill: "#5C6B63", fontSize: 11 }}
                      axisLine={{ stroke: "#E2E7E4" }}
                      tickLine={false}
                    />
                    <YAxis
                      tickFormatter={(v: number) => `${(v / 1_000_000).toFixed(1)}M`}
                      tick={{ fill: "#5C6B63", fontSize: 11 }}
                      axisLine={false}
                      tickLine={false}
                      width={44}
                    />
                    <Tooltip content={<ChartTooltip />} />
                    <Bar
                      dataKey="revenue_ron"
                      name="Net Revenue"
                      fill="#146C43"
                      radius={[3, 3, 0, 0]}
                      maxBarSize={36}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              <div className="mt-3 grid grid-cols-1 gap-4 border-t border-[#E2E7E4] pt-3 sm:grid-cols-2">
                <div>
                  <div className="mb-1.5 text-xs font-medium text-[#5C6B63]">
                    By Gender
                  </div>
                  <table className="w-full border-collapse text-left text-xs">
                    <tbody className="divide-y divide-[#E2E7E4]">
                      {data.demographics.by_sex.map((g) => (
                        <tr key={g.label}>
                          <td className="py-1.5 font-medium text-[#111A16]">{g.label}</td>
                          <td className="tabular py-1.5 text-right text-[#46544D]">
                            {formatInt(g.members)}
                          </td>
                          <td className="tabular py-1.5 text-right font-medium text-[#111A16]">
                            {formatCompactRon(g.revenue_ron)} RON
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div>
                  <div className="mb-1.5 text-xs font-medium text-[#5C6B63]">
                    Top Cardholder Regions
                  </div>
                  <table className="w-full border-collapse text-left text-xs">
                    <tbody className="divide-y divide-[#E2E7E4]">
                      {data.demographics.by_region.slice(0, 4).map((r) => (
                        <tr key={r.label}>
                          <td className="py-1.5 text-[#111A16]">{r.label}</td>
                          <td className="tabular py-1.5 text-right text-[#46544D]">
                            {formatInt(r.members)}
                          </td>
                          <td className="tabular py-1.5 text-right font-medium text-[#111A16]">
                            {formatCompactRon(r.revenue_ron)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
