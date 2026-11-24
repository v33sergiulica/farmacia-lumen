import { ArrowRight } from "lucide-react";
import { useState } from "react";
import { useAlerts } from "../api/client";
import { PanelError } from "../components/PanelError";
import { TableCardSkeleton } from "../components/Skeletons";
import { useFilters } from "../context/FilterContext";
import type { AlertCategory, AlertSeverity } from "../types/api";
import { formatRon } from "../utils/format";

const SEVERITY_STYLE: Record<
  AlertSeverity,
  { border: string; badgeBg: string; badgeText: string; label: string }
> = {
  critical: {
    border: "border-l-[#B42318]",
    badgeBg: "bg-[#FEF3F2]",
    badgeText: "text-[#B42318]",
    label: "Critical",
  },
  high: {
    border: "border-l-[#B54708]",
    badgeBg: "bg-[#FFFAEB]",
    badgeText: "text-[#B54708]",
    label: "High",
  },
  medium: {
    border: "border-l-[#146C43]",
    badgeBg: "bg-[#ECF6F0]",
    badgeText: "text-[#146C43]",
    label: "Medium",
  },
  low: {
    border: "border-l-[#94A3B8]",
    badgeBg: "bg-[#F6F7F6]",
    badgeText: "text-[#46544D]",
    label: "Low",
  },
};

const CATEGORY_LABEL: Record<AlertCategory, string> = {
  store_performance: "Store Performance",
  promotions: "Promotions & Margin",
  inventory: "Inventory & Supply",
  loyalty: "Customers & Loyalty",
  data_hygiene: "Data Hygiene",
};

export function ActionsPage() {
  const { filters, navigateWithFilters } = useFilters();
  const [severity, setSeverity] = useState<AlertSeverity | null>(null);
  const [category, setCategory] = useState<AlertCategory | null>(null);

  const { data, isLoading, isPlaceholderData, isError, error, refetch } =
    useAlerts(filters, severity, category);

  if (isError && !data) {
    return (
      <PanelError
        title="Unable to load Operational Alerts"
        message={error instanceof Error ? error.message : "Request failed"}
        onRetry={() => void refetch()}
      />
    );
  }

  return (
    <div
      className={`space-y-5 transition-opacity duration-150 ${
        isPlaceholderData ? "opacity-60" : "opacity-100"
      }`}
    >
      {/* Severity Filter & Quantified Impact Strip */}
      <section className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-[#E2E7E4] bg-white p-4">
        <div className="flex flex-wrap items-center gap-2.5">
          <div className="inline-flex rounded-lg border border-[#E2E7E4] bg-[#F6F7F6] p-1">
            {(
              [
                { id: null, label: "All" },
                { id: "critical", label: `Critical (${data?.counts.critical ?? 0})` },
                { id: "high", label: `High (${data?.counts.high ?? 0})` },
                { id: "medium", label: `Medium (${data?.counts.medium ?? 0})` },
                { id: "low", label: `Low (${data?.counts.low ?? 0})` },
              ] as const
            ).map((opt) => (
              <button
                key={opt.label}
                type="button"
                onClick={() => setSeverity(opt.id)}
                className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                  severity === opt.id
                    ? "bg-white text-[#146C43] ring-1 ring-[#E2E7E4]"
                    : "text-[#46544D] hover:text-[#111A16]"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          <select
            aria-label="Filter alert domain"
            value={category ?? ""}
            onChange={(e) =>
              setCategory((e.target.value || null) as AlertCategory | null)
            }
            className="h-8 rounded-md border border-[#E2E7E4] bg-white px-2.5 text-xs text-[#111A16] focus:border-[#146C43] focus:outline-none"
          >
            <option value="">All Domains</option>
            {Object.entries(CATEGORY_LABEL).map(([k, lbl]) => (
              <option key={k} value={k}>
                {lbl}
              </option>
            ))}
          </select>
        </div>

        <div className="text-right">
          <div className="text-[11px] font-medium text-[#5C6B63]">
            Quantified Financial Impact (Filtered)
          </div>
          <div className="tabular text-base font-semibold text-[#B42318]">
            {data ? `${formatRon(data.total_quantified_impact_ron)} RON (fără TVA)` : "—"}
          </div>
        </div>
      </section>

      {/* Dynamic Alert Cards */}
      {isLoading || !data ? (
        <TableCardSkeleton rows={6} />
      ) : data.alerts.length === 0 ? (
        <div className="rounded-lg border border-[#E2E7E4] bg-white p-8 text-center text-sm text-[#5C6B63]">
          No operational anomalies match the current filter selection.
        </div>
      ) : (
        <section className="space-y-3">
          {data.alerts.map((alert) => {
            const st = SEVERITY_STYLE[alert.severity];
            return (
              <article
                key={alert.id}
                className={`rounded-lg border border-[#E2E7E4] border-l-4 ${st.border} bg-white p-5`}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <span
                        className={`rounded px-2 py-0.5 text-[11px] font-semibold ${st.badgeBg} ${st.badgeText}`}
                      >
                        {st.label}
                      </span>
                      <span className="font-medium text-[#5C6B63]">
                        {CATEGORY_LABEL[alert.category]}
                      </span>
                      <span className="tabular font-medium text-[#111A16]">
                        · {alert.metric_highlight}
                      </span>
                    </div>
                    <h3 className="text-balance mt-1.5 text-sm font-semibold text-[#111A16]">
                      {alert.title}
                    </h3>
                  </div>

                  <div className="flex items-center gap-4">
                    {alert.ron_impact > 0 && (
                      <div className="text-right">
                        <div className="text-[11px] text-[#5C6B63]">Impact</div>
                        <div className="tabular text-sm font-semibold text-[#B42318]">
                          {formatRon(alert.ron_impact)} RON
                        </div>
                      </div>
                    )}
                    <button
                      type="button"
                      onClick={() =>
                        navigateWithFilters(
                          alert.drilldown_path,
                          alert.drilldown_filters,
                        )
                      }
                      className="inline-flex items-center gap-1 rounded-md border border-[#E2E7E4] bg-white px-3 py-1.5 text-xs font-medium text-[#146C43] hover:border-[#B7DFC9] hover:bg-[#ECF6F0]"
                    >
                      Inspect
                      <ArrowRight size={14} strokeWidth={1.5} />
                    </button>
                  </div>
                </div>

                <div className="mt-3 grid grid-cols-1 gap-3 border-t border-[#E2E7E4] pt-3 text-xs md:grid-cols-2">
                  <div>
                    <span className="font-semibold text-[#46544D]">Evidence: </span>
                    <span className="text-[#46544D]">{alert.evidence}</span>
                  </div>
                  <div>
                    <span className="font-semibold text-[#146C43]">Recommended Action: </span>
                    <span className="text-[#111A16]">{alert.recommended_action}</span>
                  </div>
                </div>
              </article>
            );
          })}
        </section>
      )}
    </div>
  );
}
