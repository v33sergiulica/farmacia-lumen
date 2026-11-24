import { ChevronDown, ChevronRight, Send, X } from "lucide-react";
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
  "Which promotions generated negative gross profit and how many lines sold below cost?",
  "List the top 10 zero-stock active SKUs by 90-day revenue across Iași Palas and Sibiu.",
  "Compare average basket value and margin between loyalty card and non-card receipts.",
];

export function AnalystDrawer({ open, onClose }: AnalystDrawerProps) {
  const { filters } = useFilters();
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalystResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isNotImplemented, setIsNotImplemented] = useState(false);
  const [showSql, setShowSql] = useState(false);

  if (!open) return null;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || loading) return;

    setLoading(true);
    setErrorMsg(null);
    setIsNotImplemented(false);
    setResult(null);

    try {
      const res = await askAnalyst(trimmed, filters);
      setResult(res);
    } catch (err) {
      if (err instanceof ApiError && err.status === 501) {
        setIsNotImplemented(true);
        setErrorMsg(err.message);
      } else {
        setErrorMsg(err instanceof Error ? err.message : "Query failed.");
      }
    } finally {
      setLoading(false);
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
        className="relative z-10 flex h-full w-full max-w-xl flex-col border-l border-[#E2E7E4] bg-white transition-transform duration-150"
      >
        <div className="flex items-center justify-between border-b border-[#E2E7E4] px-5 py-4">
          <div>
            <h2 className="text-base font-semibold text-[#111A16]">
              Ask Your Data
            </h2>
            <p className="mt-0.5 text-xs text-[#5C6B63]">
              Read-only SQL analyst over `farmacia.db` (RON fără TVA)
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
              Suggested questions
            </div>
            <div className="mt-2 flex flex-col gap-1.5">
              {STARTER_QUESTIONS.map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => setQuestion(q)}
                  className="rounded-md border border-[#E2E7E4] bg-[#F6F7F6] px-3 py-2 text-left text-xs text-[#111A16] hover:border-[#B7DFC9] hover:bg-[#ECF6F0]"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-2.5">
            <label htmlFor="analyst-q" className="block text-xs font-medium text-[#46544D]">
              Business question
            </label>
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
                POST /api/v1/analyst/ask
              </span>
              <button
                type="submit"
                disabled={loading || !question.trim()}
                className="inline-flex items-center gap-1.5 rounded-md bg-[#146C43] px-3.5 py-2 text-xs font-medium text-white hover:bg-[#0F5132] disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Send size={14} strokeWidth={1.5} />
                {loading ? "Analyzing..." : "Run Query"}
              </button>
            </div>
          </form>

          {isNotImplemented && (
            <div className="rounded-lg border border-[#FEDF89] bg-[#FFFAEB] p-4 text-xs text-[#111A16]">
              <p className="font-semibold text-[#B54708]">
                Phase 5 Integration Slot Ready (HTTP 501)
              </p>
              <p className="mt-1 text-[#46544D]">
                The frontend drawer is wired to <span className="font-mono-data">/api/v1/analyst/ask</span>.
                The headless Text-to-SQL service will be connected in Phase 5.
              </p>
            </div>
          )}

          {errorMsg && !isNotImplemented && (
            <div className="rounded-lg border border-[#FECDCA] bg-[#FEF3F2] p-4 text-xs text-[#B42318]">
              {errorMsg}
            </div>
          )}

          {result && (
            <div className="space-y-3 rounded-lg border border-[#E2E7E4] bg-[#F6F7F6] p-4">
              <p className="text-sm leading-relaxed text-[#111A16]">{result.answer}</p>

              <div className="border-t border-[#E2E7E4] pt-2.5">
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
                  Executed SQL ({result.row_count} rows · {result.execution_ms.toFixed(1)} ms)
                </button>
                {showSql && (
                  <pre className="font-mono-data mt-2 overflow-x-auto rounded border border-[#E2E7E4] bg-white p-3 text-[11px] text-[#111A16]">
                    {result.sql}
                  </pre>
                )}
              </div>

              {result.rows.length > 0 && (
                <div className="overflow-x-auto rounded border border-[#E2E7E4] bg-white">
                  <table className="w-full border-collapse text-left text-xs">
                    <thead className="border-b border-[#E2E7E4] bg-[#F6F7F6] text-[#5C6B63]">
                      <tr>
                        {result.columns.map((col) => (
                          <th key={col} className="px-2.5 py-2 font-medium">
                            {col}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#E2E7E4]">
                      {result.rows.slice(0, 20).map((row, idx) => (
                        <tr key={idx}>
                          {result.columns.map((col) => (
                            <td key={col} className="tabular px-2.5 py-1.5 text-[#111A16]">
                              {String(row[col] ?? "—")}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}
