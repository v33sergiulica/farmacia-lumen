import { Check, ChevronDown, ChevronRight, Copy, Send, X } from "lucide-react";
import { useState, type FormEvent } from "react";
import { ApiError, askAnalyst } from "../api/client";
import { useFilters } from "../context/FilterContext";
import type { AnalystResponse } from "../types/api";

interface AnalystDrawerProps {
  open: boolean;
  onClose: () => void;
}

const STARTER_QUESTIONS = [
  "Which 5 pharmacies missed their cumulative target by the largest RON margin?",
  "Which promotions lost money or sold below cost on positive-quantity sales, and by how much?",
  "Compare Vara în siguranță -15% (2025) vs -20% (2026) on revenue, discounts, and gross profit.",
  "List the top 10 zero-stock active SKUs by 90-day revenue at risk across open pharmacies.",
  "Compare loyalty card vs. non-card average basket value, margin, and dormant member count.",
];

function isNumericCell(val: unknown): boolean {
  return typeof val === "number" && Number.isFinite(val);
}

function formatCellValue(val: unknown): string {
  if (val === null || val === undefined) return "—";
  if (typeof val === "number") {
    if (Number.isInteger(val)) return val.toLocaleString("en-US");
    return val.toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }
  return String(val);
}

export function AnalystDrawer({ open, onClose }: AnalystDrawerProps) {
  const { filters, hasActiveFilters } = useFilters();
  const [question, setQuestion] = useState("");
  const [attachFilters, setAttachFilters] = useState(true);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalystResponse | null>(null);
  const [errorInfo, setErrorInfo] = useState<{ status?: number; message: string } | null>(
    null,
  );
  const [showSql, setShowSql] = useState(false);
  const [copiedSql, setCopiedSql] = useState(false);

  if (!open) return null;

  async function runQuestion(rawQuestion: string) {
    const trimmed = rawQuestion.trim();
    if (!trimmed || loading) return;

    setLoading(true);
    setErrorInfo(null);
    setResult(null);
    setCopiedSql(false);

    try {
      const res = await askAnalyst(
        trimmed,
        attachFilters && hasActiveFilters
          ? filters
          : {
              start_date: filters.start_date,
              end_date: filters.end_date,
              region_id: null,
              store_id: null,
              category_id: null,
              subcategory_id: null,
            },
      );
      setResult(res);
    } catch (err) {
      if (err instanceof ApiError) {
        setErrorInfo({ status: err.status, message: err.message });
      } else {
        setErrorInfo({
          message: err instanceof Error ? err.message : "Query request failed.",
        });
      }
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    void runQuestion(question);
  }

  async function handleCopySql() {
    if (!result?.sql) return;
    try {
      await navigator.clipboard.writeText(result.sql);
      setCopiedSql(true);
      window.setTimeout(() => setCopiedSql(false), 1800);
    } catch {
      // clipboard unavailable
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div
        className="fixed inset-0 bg-[#111A16]/20 transition-opacity duration-150"
        onClick={onClose}
        aria-hidden="true"
      />
      <aside
        aria-label="Ask Your Data Analyst"
        className="relative z-10 flex h-full w-full max-w-2xl flex-col border-l border-[#E2E7E4] bg-white transition-transform duration-150"
      >
        <div className="flex items-center justify-between border-b border-[#E2E7E4] px-5 py-4">
          <div>
            <h2 className="text-base font-semibold text-[#111A16]">
              Ask Your Data
            </h2>
            <p className="mt-0.5 text-xs text-[#5C6B63]">
              Read-only Text-to-SQL analyst over <span className="font-mono-data">farmacia.db</span> · all values in RON (fără TVA)
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close Ask Your Data"
            className="rounded-md p-1.5 text-[#5C6B63] hover:bg-[#F6F7F6] hover:text-[#111A16]"
          >
            <X size={18} strokeWidth={1.5} />
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto p-5">
          <div>
            <div className="text-xs font-medium text-[#5C6B63]">
              Quick analytical questions
            </div>
            <div className="mt-2 flex flex-col gap-1.5">
              {STARTER_QUESTIONS.map((q) => (
                <button
                  key={q}
                  type="button"
                  disabled={loading}
                  onClick={() => {
                    setQuestion(q);
                    void runQuestion(q);
                  }}
                  className="rounded-md border border-[#E2E7E4] bg-[#F6F7F6] px-3 py-2 text-left text-xs text-[#111A16] transition-colors hover:border-[#B7DFC9] hover:bg-[#ECF6F0] disabled:opacity-50"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-2.5">
            <div className="flex items-center justify-between">
              <label htmlFor="analyst-q" className="text-xs font-medium text-[#46544D]">
                Business question
              </label>
              {hasActiveFilters && (
                <label className="inline-flex cursor-pointer items-center gap-1.5 text-xs text-[#5C6B63]">
                  <input
                    type="checkbox"
                    checked={attachFilters}
                    onChange={(e) => setAttachFilters(e.target.checked)}
                    className="h-3.5 w-3.5 accent-[#146C43]"
                  />
                  Include active dashboard filters
                </label>
              )}
            </div>
            <textarea
              id="analyst-q"
              rows={3}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask about store variances, product margins, stockouts, or customer cohorts..."
              className="w-full rounded-md border border-[#E2E7E4] bg-white p-3 text-sm text-[#111A16] placeholder:text-[#5C6B63] focus:border-[#146C43] focus:outline-none"
            />
            <div className="flex items-center justify-between">
              <span className="font-mono-data text-[11px] text-[#5C6B63]">
                Read-only SELECT/WITH · max 200 rows
              </span>
              <button
                type="submit"
                disabled={loading || !question.trim()}
                className="inline-flex items-center gap-1.5 rounded-md bg-[#146C43] px-3.5 py-2 text-xs font-medium text-white transition-colors hover:bg-[#0F5132] disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Send size={14} strokeWidth={1.5} />
                {loading ? "Running SQL..." : "Run Query"}
              </button>
            </div>
          </form>

          {loading && (
            <div className="space-y-2.5 rounded-lg border border-[#E2E7E4] bg-[#F6F7F6] p-4">
              <div className="h-3.5 w-48 animate-pulse rounded bg-[#E2E7E4]" />
              <div className="h-3 w-full animate-pulse rounded bg-[#E2E7E4]" />
              <div className="h-3 w-5/6 animate-pulse rounded bg-[#E2E7E4]" />
            </div>
          )}

          {errorInfo && (
            <div
              className={`rounded-lg border p-4 text-xs ${
                errorInfo.status === 503
                  ? "border-[#FEDF89] bg-[#FFFAEB] text-[#111A16]"
                  : "border-[#FECDCA] bg-[#FEF3F2] text-[#B42318]"
              }`}
            >
              <p
                className={`font-semibold ${
                  errorInfo.status === 503 ? "text-[#B54708]" : "text-[#B42318]"
                }`}
              >
                {errorInfo.status === 503
                  ? "AI Provider Not Configured"
                  : errorInfo.status === 400
                    ? "Query Blocked by Read-Only Guardrail"
                    : "Unable to Complete Query"}
              </p>
              <p className="mt-1 text-[#46544D]">{errorInfo.message}</p>
            </div>
          )}

          {result && (
            <div className="space-y-3 rounded-lg border border-[#E2E7E4] bg-[#F6F7F6] p-4">
              <div className="text-sm leading-relaxed text-[#111A16]">
                {result.answer}
              </div>

              {/* Collapsible Executed SQL with Copy */}
              <div className="border-t border-[#E2E7E4] pt-2.5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <button
                    type="button"
                    onClick={() => setShowSql((s) => !s)}
                    className="inline-flex items-center gap-1 text-xs font-medium text-[#46544D] hover:text-[#111A16]"
                  >
                    {showSql ? (
                      <ChevronDown size={14} strokeWidth={1.5} />
                    ) : (
                      <ChevronRight size={14} strokeWidth={1.5} />
                    )}
                    <span>
                      Executed SQL ({result.row_count}
                      {result.truncated ? "+" : ""} rows · {result.execution_ms.toFixed(1)} ms
                      {result.retries_used > 0 ? ` · ${result.retries_used} retry` : ""})
                    </span>
                  </button>
                  {showSql && (
                    <button
                      type="button"
                      onClick={() => void handleCopySql()}
                      className="inline-flex items-center gap-1 rounded border border-[#E2E7E4] bg-white px-2 py-1 text-[11px] font-medium text-[#46544D] hover:text-[#111A16]"
                    >
                      {copiedSql ? (
                        <>
                          <Check size={12} strokeWidth={1.5} className="text-[#146C43]" />
                          Copied
                        </>
                      ) : (
                        <>
                          <Copy size={12} strokeWidth={1.5} />
                          Copy SQL
                        </>
                      )}
                    </button>
                  )}
                </div>
                {showSql && (
                  <pre className="font-mono-data mt-2 overflow-x-auto rounded border border-[#E2E7E4] bg-white p-3 text-[11px] leading-relaxed text-[#111A16]">
                    {result.sql}
                  </pre>
                )}
              </div>

              {/* Tabular Preview */}
              {result.rows.length > 0 && (
                <div className="overflow-x-auto rounded border border-[#E2E7E4] bg-white">
                  <table className="w-full border-collapse text-left text-xs">
                    <thead className="border-b border-[#E2E7E4] bg-[#F6F7F6] text-[#5C6B63]">
                      <tr>
                        {result.columns.map((col) => {
                          const numericCol = isNumericCell(result.rows[0]?.[col]);
                          return (
                            <th
                              key={col}
                              className={`px-2.5 py-2 font-medium ${
                                numericCol ? "text-right" : "text-left"
                              }`}
                            >
                              {col}
                            </th>
                          );
                        })}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#E2E7E4]">
                      {result.rows.slice(0, 25).map((row, idx) => (
                        <tr key={idx} className="hover:bg-[#F6F7F6]">
                          {result.columns.map((col) => {
                            const val = row[col];
                            const numeric = isNumericCell(val);
                            return (
                              <td
                                key={col}
                                className={`tabular px-2.5 py-1.5 text-[#111A16] ${
                                  numeric ? "text-right" : "text-left"
                                }`}
                              >
                                {formatCellValue(val)}
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {result.rows.length > 25 && (
                    <div className="border-t border-[#E2E7E4] bg-[#F6F7F6] px-2.5 py-1.5 text-[11px] text-[#5C6B63]">
                      Showing first 25 of {result.row_count} returned rows
                      {result.truncated ? " (capped at 200 rows)" : ""}.
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}
