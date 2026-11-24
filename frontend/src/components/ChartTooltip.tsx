import { formatPct, formatRon } from "../utils/format";

export interface TooltipEntry {
  name?: string;
  value?: number | string;
  color?: string;
  dataKey?: string;
  payload?: Record<string, unknown>;
}

interface ChartTooltipProps {
  active?: boolean;
  payload?: TooltipEntry[];
  label?: string;
  unitMode?: "ron" | "pct" | "mixed";
  decimals?: number;
}

export function ChartTooltip({
  active,
  payload,
  label,
  unitMode = "ron",
  decimals = 0,
}: ChartTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;

  return (
    <div className="rounded-md border border-[#E2E7E4] bg-white px-3 py-2 text-xs text-[#111A16] shadow-xs">
      {label && (
        <div className="mb-1.5 border-b border-[#E2E7E4] pb-1 font-medium text-[#111A16]">
          {label}
        </div>
      )}
      <div className="space-y-1">
        {payload.map((entry, idx) => {
          const raw = entry.value;
          const num = typeof raw === "number" ? raw : Number(raw);
          const nameStr = String(entry.name ?? entry.dataKey ?? "");
          const isPct =
            unitMode === "pct" ||
            nameStr.includes("%") ||
            nameStr.toLowerCase().includes("margin") ||
            nameStr.toLowerCase().includes("attainment") ||
            nameStr.toLowerCase().includes("uplift") ||
            nameStr.toLowerCase().includes("share");
          const isCount =
            nameStr.toLowerCase().includes("sku") ||
            nameStr.toLowerCase().includes("units") ||
            nameStr.toLowerCase().includes("members") ||
            nameStr.toLowerCase().includes("receipt");

          let formatted: string;
          if (!Number.isFinite(num)) {
            formatted = String(raw ?? "—");
          } else if (isPct) {
            formatted = formatPct(num, 1);
          } else if (isCount) {
            formatted = Math.round(num).toLocaleString("en-US");
          } else {
            formatted = `${formatRon(num, decimals)} RON (fără TVA)`;
          }

          return (
            <div key={idx} className="flex items-center justify-between gap-4">
              <span className="flex items-center gap-1.5 text-[#46544D]">
                <span
                  className="inline-block h-2 w-2 rounded-xs"
                  style={{ backgroundColor: entry.color || "#146C43" }}
                />
                {nameStr}
              </span>
              <span className="tabular font-medium text-[#111A16]">{formatted}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
