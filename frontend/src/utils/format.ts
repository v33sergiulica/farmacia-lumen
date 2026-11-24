export const DB_MIN_DATE = "2025-05-01";
export const DB_MAX_DATE = "2026-10-31";

export interface DatePreset {
  id: string;
  label: string;
  start_date: string;
  end_date: string;
}

// All relative presets are strictly anchored to DB_MAX_DATE (2026-10-31), never new Date().
export const DATE_PRESETS: DatePreset[] = [
  { id: "full", label: "Full 18M", start_date: "2025-05-01", end_date: "2026-10-31" },
  { id: "ytd26", label: "2026 YTD", start_date: "2026-01-01", end_date: "2026-10-31" },
  { id: "q3_26", label: "Q3 2026", start_date: "2026-07-01", end_date: "2026-09-30" },
  { id: "90d", label: "Last 90D", start_date: "2026-08-03", end_date: "2026-10-31" },
  { id: "30d", label: "Last 30D", start_date: "2026-10-02", end_date: "2026-10-31" },
];

const numFmt0 = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

const numFmt2 = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function formatInt(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return numFmt0.format(Math.round(value));
}

export function formatRon(value: number | null | undefined, decimals = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return decimals === 2 ? numFmt2.format(value) : numFmt0.format(Math.round(value));
}

export function formatCompactRon(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 1_000_000) return `${sign}${(abs / 1_000_000).toFixed(2)}M`;
  if (abs >= 1_000) return `${sign}${(abs / 1_000).toFixed(1)}k`;
  return `${sign}${Math.round(abs)}`;
}

export function formatAxisRon(value: number): string {
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (Math.abs(value) >= 1_000) return `${Math.round(value / 1_000)}k`;
  return String(Math.round(value));
}

export function formatPct(value: number | null | undefined, decimals = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${value.toFixed(decimals)}%`;
}

export function formatSignedPct(value: number | null | undefined, decimals = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(decimals)}%`;
}

export function shortStoreName(nume: string): string {
  return nume.replace(/^Farmacia Lumen\s+/i, "");
}
