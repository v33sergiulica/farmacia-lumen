"""Headless AI Analyst: domain-grounded Text-to-SQL with strict read-only guardrails."""

from __future__ import annotations

import json
import re
import shutil
import sqlite3
import subprocess
import time
from functools import lru_cache
from typing import Any

from ..config import settings
from ..db import get_ro_connection
from ..schemas import AnalystResponse


class AnalystConfigError(RuntimeError):
    """Raised when the configured LLM provider or credentials/CLI are unavailable."""


class SqlSecurityError(ValueError):
    """Raised when generated SQL violates read-only or single-statement guardrails."""


class AnalystExecutionError(RuntimeError):
    """Raised when SQL generation or read-only execution fails after retry."""


FORBIDDEN_SQL_KEYWORDS: frozenset[str] = frozenset(
    {
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "ALTER",
        "CREATE",
        "REPLACE",
        "TRUNCATE",
        "ATTACH",
        "DETACH",
        "PRAGMA",
        "VACUUM",
        "REINDEX",
        "ANALYZE",
        "BEGIN",
        "COMMIT",
        "ROLLBACK",
        "SAVEPOINT",
        "RELEASE",
        "LOAD_EXTENSION",
        "ZEROBLOB",
        "RANDOMBLOB",
    }
)

FORBIDDEN_KEYWORD_RE = re.compile(
    r"\b(" + "|".join(sorted(FORBIDDEN_SQL_KEYWORDS)) + r")\b",
    re.IGNORECASE,
)

CODE_FENCE_RE = re.compile(r"```(?:sql|sqlite)?\s*(.*?)\s*```", re.IGNORECASE | re.DOTALL)


def _extract_sql_text(raw: str) -> str:
    text = raw.strip()
    m = CODE_FENCE_RE.search(text)
    if m:
        text = m.group(1).strip()
    # Remove any leading "SQL:" prefix models sometimes emit
    text = re.sub(r"^(?:sql|query)\s*:\s*", "", text, flags=re.IGNORECASE).strip()
    return text


def _strip_literals_and_comments(sql: str) -> str:
    """Replace SQL string literals and strip comments for safe static inspection."""
    out: list[str] = []
    i = 0
    n = len(sql)
    while i < n:
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < n else ""
        # Line comment: -- ...
        if ch == "-" and nxt == "-":
            i += 2
            while i < n and sql[i] != "\n":
                i += 1
            out.append(" ")
            continue
        # Block comment: /* ... */
        if ch == "/" and nxt == "*":
            end = sql.find("*/", i + 2)
            if end == -1:
                raise SqlSecurityError("Unterminated block comment in SQL query.")
            i = end + 2
            out.append(" ")
            continue
        # Single-quoted string literal
        if ch == "'":
            i += 1
            while i < n:
                if sql[i] == "'":
                    if i + 1 < n and sql[i + 1] == "'":
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            out.append(" '' ")
            continue
        # Double-quoted identifier
        if ch == '"':
            i += 1
            while i < n:
                if sql[i] == '"':
                    if i + 1 < n and sql[i + 1] == '"':
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            out.append(' "" ')
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def validate_read_only_sql(raw_sql: str) -> str:
    """Validate that SQL is a single read-only SELECT or WITH...SELECT statement."""
    cleaned = _extract_sql_text(raw_sql)
    if not cleaned:
        raise SqlSecurityError("Generated SQL is empty.")

    stripped = _strip_literals_and_comments(cleaned).strip()
    if stripped.endswith(";"):
        stripped = stripped[:-1].strip()
    if ";" in stripped:
        raise SqlSecurityError("Multiple SQL statements (semicolons) are strictly forbidden.")

    # Trim single optional trailing semicolon on executable SQL as well
    exec_sql = cleaned.rstrip()
    if exec_sql.endswith(";"):
        exec_sql = exec_sql[:-1].rstrip()

    first_token_match = re.match(r"^\s*([A-Za-z_]+)", stripped)
    if not first_token_match:
        raise SqlSecurityError("SQL must begin with SELECT or WITH.")
    first_kw = first_token_match.group(1).upper()
    if first_kw not in {"SELECT", "WITH"}:
        raise SqlSecurityError(
            f"Only read-only SELECT or WITH queries are permitted (got '{first_kw}')."
        )

    forbidden_match = FORBIDDEN_KEYWORD_RE.search(stripped)
    if forbidden_match:
        raise SqlSecurityError(
            f"Forbidden SQL keyword detected: '{forbidden_match.group(1).upper()}'."
        )

    # For WITH queries, ensure SELECT actually appears outside comments/literals
    if first_kw == "WITH" and not re.search(r"\bSELECT\b", stripped, re.IGNORECASE):
        raise SqlSecurityError("CTE query must contain a SELECT statement.")

    return exec_sql


@lru_cache(maxsize=1)
def get_schema_ddl() -> str:
    """Read compact CREATE TABLE schema once from SQLite in read-only mode."""
    conn = get_ro_connection()
    try:
        rows = conn.execute(
            """
            SELECT sql FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%' AND sql IS NOT NULL
            ORDER BY name
            """
        ).fetchall()
        return "\n\n".join(str(r["sql"]).strip() + ";" for r in rows)
    finally:
        conn.close()


DOMAIN_RULES_PROMPT = """
BUSINESS & DATA HYGIENE RULES (MANDATORY):
1. Currency & VAT: ALL monetary columns (`valoare_fara_tva`, `cost`, `profit`, `reducere`, `target_vanzari`, `pret_fara_tva`, `cost_achizitie`) are in RON excluding VAT (`RON fără TVA`).
2. Dataset timeframe: `2025-05-01` through `2026-10-31` (18 months, 21 pharmacies across 8 regions).
3. Returns accounting: Return lines in `vanzari` have `cantitate < 0` (negative `valoare_fara_tva` and negative `profit`).
   - Net revenue = `SUM(v.valoare_fara_tva)`.
   - Gross revenue = `SUM(CASE WHEN v.cantitate > 0 THEN v.valoare_fara_tva ELSE 0 END)`.
   - For below-cost / negative-margin promotion diagnostics, ALWAYS filter `v.cantitate > 0 AND v.profit < 0` so customer returns are never miscounted as below-cost promo sales.
4. Test promotion exclusion: ALWAYS exclude `oferte.id = 13` ("TEST - nu folosi") from campaign analytics (`o.id != 13 AND LOWER(o.nume) NOT LIKE '%test%'`) unless the user explicitly asks about test promotions.
5. Inventory snapshot & stockouts: `magazin_stoc` is a closing stock snapshot as of `2026-10-31`.
   - For active stockout queries, ALWAYS filter `p.activ = 1` (excludes discontinued SKU #180 `Termometru infraroșu Termix`) and `m.inchis_la IS NULL` (excludes closed store Deva #16).
   - 90-day velocity ending `2026-10-31` uses `b.cand >= '2026-08-03 00:00:00' AND b.cand < '2026-11-01 00:00:00'`.
   - Current unit cost is in `preturi` where `pana_la IS NULL`.
6. Category hierarchy: `categorii` has 2 levels: L1 parents (`id_parinte IS NULL`) and L2 subcategories (`id_parinte IS NOT NULL`). Every product's `produse.id_categorie` points to an L2 subcategory. Join `categorii c2 ON c2.id = p.id_categorie LEFT JOIN categorii c1 ON c1.id = c2.id_parinte` to group by L1 parent category.
7. Partial-period stores: Deva (`id = 16`) closed `2026-06-30`; Cluj Mărăști (`id = 18`) opened `2026-03-16`.
8. Target table & anti-fan-out rule (CRITICAL): `target_lunar` is at `(id_magazin, luna)` monthly grain (`luna` is `YYYY-MM`).
   - NEVER join `target_lunar` directly to unaggregated `bonuri`/`vanzari` rows (that causes a fan-out multiplication of `target_vanzari` by every receipt/line item!).
   - ALWAYS pre-aggregate sales in one CTE (e.g. `sales_cte` grouped by `id_magazin` or `(id_magazin, substr(b.cand,1,7))`) and pre-aggregate `target_lunar` in a separate CTE (e.g. `target_cte` grouped by `id_magazin` or `(id_magazin, luna)`), then JOIN the two aggregated CTEs.
   - Apply the same pre-aggregation CTE rule whenever combining `vanzari` with `magazin_stoc` or `receptii`.
9. Performance & SQLite dialect:
   - Write standard SQLite SQL ONLY.
   - Prefer index-friendly bounds `b.cand >= 'YYYY-MM-DD 00:00:00' AND b.cand < 'YYYY-MM-DD 00:00:00'` instead of wrapping `b.cand` in `substr()` inside `WHERE`.
   - Use concise readable column aliases and include an appropriate `LIMIT` (never exceeding 200 rows).
   - Output ONLY the single SQL query — no explanations, no markdown prose outside the SQL.
""".strip()


def _format_filter_context(filters: dict[str, str | int | None] | None) -> str:
    if not filters:
        return ""
    active: list[str] = []
    start_d = filters.get("start_date")
    end_d = filters.get("end_date")
    if (start_d and start_d != settings.default_start_date) or (
        end_d and end_d != settings.default_end_date
    ):
        active.append(
            f"date_range={start_d or settings.default_start_date}..{end_d or settings.default_end_date}"
        )
    for key in ("region_id", "store_id", "category_id", "subcategory_id"):
        val = filters.get(key)
        if val is not None and val != "":
            active.append(f"{key}={val}")
    if not active:
        return ""
    return (
        "\nACTIVE DASHBOARD FILTERS CONTEXT: "
        + ", ".join(active)
        + ". Apply these filters ONLY if the user refers to the current view/selection (e.g. 'here', 'this store', 'filtered view'); if the user asks about the full chain or names a specific store/period, answer what the user explicitly asked."
    )


def _call_llm(system_prompt: str, user_prompt: str) -> str:
    """Invoke the configured headless LLM provider without logging secrets."""
    provider = settings.analyst_provider.strip().lower()

    if provider == "gemini_api":
        api_key = (settings.gemini_api_key or "").strip()
        if not api_key or api_key == "your_gemini_api_key_here":
            raise AnalystConfigError(
                "GEMINI_API_KEY is not configured in .env. Set GEMINI_API_KEY or switch ANALYST_PROVIDER to gemini_cli / claude_cli."
            )
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise AnalystConfigError(
                "google-genai package is not installed in the backend environment."
            ) from exc

        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=25_000,
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )
        candidate_models = [settings.gemini_model]
        if "gemini-3.1-flash-lite" not in candidate_models:
            candidate_models.append("gemini-3.1-flash-lite")

        last_exc: Exception | None = None
        for model_name in candidate_models:
            try:
                cfg_kwargs: dict[str, Any] = {
                    "system_instruction": system_prompt,
                    "temperature": 0.0,
                }
                if "gemini-3" in model_name.lower():
                    cfg_kwargs["thinking_config"] = types.ThinkingConfig(
                        thinking_level="MINIMAL"
                    )
                resp = client.models.generate_content(
                    model=model_name,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(**cfg_kwargs),
                )
                text = (resp.text or "").strip()
                if not text:
                    raise AnalystExecutionError("Gemini API returned an empty response.")
                return text
            except AnalystExecutionError:
                raise
            except Exception as exc:
                last_exc = exc
                code = getattr(exc, "code", None)
                # Fail over once ONLY on retired model (404), transient overload (503), or deadline (504); never loop on 429
                if code in (404, 503, 504):
                    continue
                break

        status_code = getattr(last_exc, "code", None) if last_exc else None
        err_msg = (
            str(getattr(last_exc, "message", "") or type(last_exc).__name__)[:160]
            if last_exc
            else "Unknown error"
        )
        raise AnalystExecutionError(
            f"Gemini API call failed ({status_code or 'error'}): {err_msg}"
        ) from last_exc

    if provider in {"gemini_cli", "claude_cli"}:
        binary = (
            settings.gemini_cli_bin if provider == "gemini_cli" else settings.claude_cli_bin
        )
        exe = shutil.which(binary)
        if not exe:
            raise AnalystConfigError(
                f"Headless CLI '{binary}' for provider '{provider}' was not found in PATH."
            )
        combined = f"{system_prompt}\n\nUSER REQUEST:\n{user_prompt}"
        try:
            # Pass prompt via stdin with shell=False so user text can never inject CLI flags
            proc = subprocess.run(
                [exe, "-p"],
                input=combined,
                capture_output=True,
                text=True,
                timeout=45,
                shell=False,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise AnalystExecutionError(f"Headless CLI '{binary}' timed out.") from exc
        if proc.returncode != 0:
            err_snippet = (proc.stderr or proc.stdout or "").strip()[:200]
            raise AnalystExecutionError(
                f"Headless CLI '{binary}' exited with code {proc.returncode}: {err_snippet}"
            )
        text = proc.stdout.strip()
        if not text:
            raise AnalystExecutionError(f"Headless CLI '{binary}' returned empty output.")
        return text

    raise AnalystConfigError(
        f"Unsupported ANALYST_PROVIDER '{provider}'. Expected one of: gemini_api, gemini_cli, claude_cli."
    )


def execute_read_only_sql(
    sql: str,
    *,
    max_rows: int | None = None,
    timeout_sec: float | None = None,
) -> tuple[list[str], list[dict[str, Any]], bool, float]:
    """Execute validated read-only SQL on mode=ro SQLite with timeout and hard row cap."""
    limit_rows = max_rows if max_rows is not None else settings.analyst_max_rows
    deadline = time.monotonic() + (
        timeout_sec if timeout_sec is not None else settings.analyst_query_timeout_sec
    )

    def _progress_check() -> int:
        return 1 if time.monotonic() > deadline else 0

    conn = get_ro_connection()
    try:
        conn.set_progress_handler(_progress_check, 5_000)
        t0 = time.perf_counter()
        cur = conn.execute(sql)
        columns = [desc[0] for desc in (cur.description or [])]
        fetched = cur.fetchmany(limit_rows + 1)
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        truncated = len(fetched) > limit_rows
        rows_slice = fetched[:limit_rows]
        rows = [{col: row[col] for col in columns} for row in rows_slice]
        return columns, rows, truncated, elapsed_ms
    except sqlite3.OperationalError as exc:
        if "interrupted" in str(exc).lower():
            timeout_val = (
                timeout_sec if timeout_sec is not None else settings.analyst_query_timeout_sec
            )
            raise sqlite3.OperationalError(
                f"Query exceeded {timeout_val:.1f}s execution timeout (interrupted by progress handler)."
            ) from exc
        raise
    finally:
        conn.set_progress_handler(None, 0)
        conn.close()


def _generate_sql(question: str, filters: dict[str, str | int | None] | None) -> str:
    schema_ddl = get_schema_ddl()
    system_prompt = (
        "You are a senior SQLite BI engineer for Farmacia Lumen (a Romanian pharmacy chain).\n"
        "Convert the user's business question into a single read-only SQLite SELECT or WITH...SELECT query.\n\n"
        f"EXACT SQLITE SCHEMA:\n{schema_ddl}\n\n{DOMAIN_RULES_PROMPT}"
    )
    user_prompt = f"Question: {question}{_format_filter_context(filters)}\n\nReturn ONLY the SQLite query."
    return _call_llm(system_prompt, user_prompt)


def _repair_sql(
    question: str,
    failed_sql: str,
    sqlite_error: str,
    filters: dict[str, str | int | None] | None,
) -> str:
    schema_ddl = get_schema_ddl()
    system_prompt = (
        "You are a senior SQLite BI engineer repairing a failed read-only SQLite query.\n"
        f"EXACT SQLITE SCHEMA:\n{schema_ddl}\n\n{DOMAIN_RULES_PROMPT}"
    )
    user_prompt = (
        f"Original Question: {question}{_format_filter_context(filters)}\n\n"
        f"Failed SQL:\n{failed_sql}\n\n"
        f"SQLite Error: {sqlite_error}\n\n"
        "Fix the SQL query so it executes cleanly in SQLite and answers the question. Return ONLY the repaired SQL."
    )
    return _call_llm(system_prompt, user_prompt)


def _synthesize_answer(
    question: str,
    sql: str,
    columns: list[str],
    rows: list[dict[str, Any]],
    truncated: bool,
) -> str:
    preview_rows = rows[:30]
    system_prompt = (
        "You are an executive BI analyst for Farmacia Lumen. Write a concise, factual answer in 2-4 sentences "
        "grounded strictly in the SQL query result below. Never invent numbers not present in the result. "
        "Explicitly label every monetary figure as 'RON (fără TVA)'. Format large numbers with commas and "
        "percentages with 1-2 decimals. Do not include raw SQL in the prose answer."
    )
    payload = {
        "question": question,
        "columns": columns,
        "total_returned_rows": len(rows),
        "truncated_at_row_cap": truncated,
        "preview_rows": preview_rows,
    }
    user_prompt = (
        f"Executed SQL:\n{sql}\n\n"
        f"Result JSON:\n{json.dumps(payload, ensure_ascii=False)}\n\n"
        "Provide a clear, executive-ready answer."
    )
    return _call_llm(system_prompt, user_prompt)


def answer_question(
    question: str,
    filters: dict[str, str | int | None] | None = None,
) -> AnalystResponse:
    """Full Text-to-SQL pipeline: generate -> validate -> execute (+1x retry) -> synthesize."""
    raw_sql = _generate_sql(question, filters)
    validated_sql = validate_read_only_sql(raw_sql)

    retries_used = 0
    try:
        columns, rows, truncated, exec_ms = execute_read_only_sql(validated_sql)
    except sqlite3.Error as first_err:
        retries_used = 1
        repaired_raw = _repair_sql(question, validated_sql, str(first_err), filters)
        validated_sql = validate_read_only_sql(repaired_raw)
        try:
            columns, rows, truncated, exec_ms = execute_read_only_sql(validated_sql)
        except sqlite3.Error as second_err:
            raise AnalystExecutionError(
                f"SQLite execution failed after automatic retry: {second_err}"
            ) from second_err

    answer = _synthesize_answer(question, validated_sql, columns, rows, truncated)

    return AnalystResponse(
        answer=answer,
        sql=validated_sql,
        columns=columns,
        rows=rows,
        row_count=len(rows),
        truncated=truncated,
        execution_ms=exec_ms,
        retries_used=retries_used,
        provider=settings.analyst_provider,
    )
