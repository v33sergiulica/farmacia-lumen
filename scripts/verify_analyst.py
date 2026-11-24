"""Security guardrail tests, SQLite timeout test, and live Q&A verification for Phase 5.

NOTE: Never reads or prints .env or any API key values.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.config import settings  # noqa: E402
from backend.app.main import app  # noqa: E402
from backend.app.services.analyst import (  # noqa: E402
    SqlSecurityError,
    answer_question,
    execute_read_only_sql,
    validate_read_only_sql,
)


def run_security_and_guardrail_tests() -> None:
    print("[STEP 1] Testing SQL read-only validator against 12 malicious payloads...", flush=True)
    malicious_queries = [
        ("DROP TABLE", "DROP TABLE vanzari"),
        ("ATTACH DATABASE", "ATTACH DATABASE 'evil.db' AS evil"),
        ("Stacked DELETE", "SELECT COUNT(*) FROM bonuri; DELETE FROM bonuri"),
        ("PRAGMA write", "PRAGMA writable_schema = ON"),
        ("INSERT", "INSERT INTO regiuni (id, nume) VALUES (99, 'Hack')"),
        ("UPDATE", "UPDATE produse SET activ = 0 WHERE id = 1"),
        ("ALTER TABLE", "ALTER TABLE magazine ADD COLUMN hacked TEXT"),
        ("VACUUM", "VACUUM"),
        ("CTE DELETE", "WITH x AS (SELECT 1) DELETE FROM vanzari"),
        ("Stacked via newline", "SELECT 1 FROM regiuni;\nDROP TABLE magazine;"),
        ("Block comment bypass", "/* ok */ DELETE FROM bonuri"),
        ("Multiple SELECTs", "SELECT 1; SELECT 2"),
        ("Memory DoS zeroblob", "SELECT zeroblob(1000000000)"),
        ("Memory DoS randomblob", "SELECT randomblob(1000000000)"),
    ]

    for label, bad_sql in malicious_queries:
        blocked = False
        try:
            validate_read_only_sql(bad_sql)
        except SqlSecurityError:
            blocked = True
        assert blocked, f"SECURITY FAILURE: '{label}' was NOT blocked: {bad_sql}"
    print(
        f"[PASS] All {len(malicious_queries)} malicious/mutating SQL payloads blocked before SQLite.",
        flush=True,
    )

    print("[STEP 2] Testing valid fenced CTE SQL normalization...", flush=True)
    valid_sql = validate_read_only_sql(
        "```sql\nWITH s AS (SELECT id, nume FROM magazine WHERE inchis_la IS NULL) SELECT * FROM s LIMIT 5;\n```"
    )
    assert valid_sql.upper().startswith("WITH ") and not valid_sql.endswith(";")
    print("[PASS] Valid fenced WITH...SELECT query accepted and normalized.", flush=True)

    print("[STEP 3] Testing SQLite progress-handler hard execution timeout...", flush=True)
    t0 = time.perf_counter()
    timed_out = False
    try:
        execute_read_only_sql(
            "WITH RECURSIVE cnt(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM cnt) SELECT COUNT(*) FROM cnt",
            timeout_sec=0.15,
        )
    except sqlite3.OperationalError as exc:
        timed_out = "timeout" in str(exc).lower() or "interrupted" in str(exc).lower()
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    assert timed_out, "SQLite progress handler failed to abort infinite query!"
    print(f"[PASS] SQLite progress handler aborted runaway query in {elapsed_ms:.1f} ms.", flush=True)

    print("[STEP 4] Testing 1x automatic SQLite error self-correction retry...", flush=True)
    calls = {"n": 0}

    def fake_llm(_sys: str, _usr: str) -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            return "SELECT COUNT(*) AS cnt FROM nonexistent_table_xyz"
        if calls["n"] == 2:
            return "SELECT COUNT(*) AS cnt FROM regiuni"
        return "There are 8 regions in Farmacia Lumen (all monetary metrics are in RON fără TVA)."

    with patch("backend.app.services.analyst._call_llm", side_effect=fake_llm):
        res = answer_question("How many regions are there?")
        assert res.retries_used == 1, f"Expected retries_used=1, got {res.retries_used}"
        assert res.row_count == 1 and res.rows[0]["cnt"] == 8
    print("[PASS] 1x automatic SQLite self-correction retry verified (retries_used=1).", flush=True)


def run_live_qa_tests() -> None:
    settings.warm_cache_on_startup = False
    questions = [
        (
            "Q1: Chain 18M Totals",
            "What is the total net revenue, gross profit, and total receipt count across all pharmacies over the full 18 months?",
            lambda resp: (
                any(
                    abs(float(v) - 47680504.42) < 1.0
                    for row in resp["rows"]
                    for v in row.values()
                    if isinstance(v, (int, float))
                )
                and any(
                    abs(float(v) - 15052057.43) < 1.0
                    for row in resp["rows"]
                    for v in row.values()
                    if isinstance(v, (int, float))
                )
                and any(
                    int(v) == 459959
                    for row in resp["rows"]
                    for v in row.values()
                    if isinstance(v, (int, float))
                )
            ),
        ),
        (
            "Q2: Worst Target Attainment Store",
            "Which single pharmacy had the lowest cumulative target attainment percentage across the dataset, and what was its attainment percentage and RON variance against target?",
            lambda resp: (
                "Tomis Nord" in resp["answer"]
                or any("Tomis Nord" in str(v) for row in resp["rows"] for v in row.values())
            ),
        ),
        (
            "Q3: Net-Loss Promotion & Below-Cost Lines",
            "Which active promotion had negative net gross profit, what was its net profit in RON, and how many positive-quantity lines sold below cost?",
            lambda resp: (
                "Somn" in resp["answer"]
                or any("Somn" in str(v) for row in resp["rows"] for v in row.values())
            )
            and any(
                abs(float(v) - (-4507.0)) < 2.0 or abs(float(v) - 4507.0) < 2.0
                for row in resp["rows"]
                for v in row.values()
                if isinstance(v, (int, float))
            ),
        ),
    ]

    print(
        f"\n[STEP 5] Running 3 live end-to-end questions via provider='{settings.analyst_provider}' (model='{settings.gemini_model}', warmup=False):",
        flush=True,
    )
    with TestClient(app) as client:
        for idx, (label, q_text, check_fn) in enumerate(questions):
            if idx > 0:
                print("  (pausing 3s to respect API RPM limits...)", flush=True)
                time.sleep(3.0)
            print(f"\n  -> Calling {label}...", flush=True)
            t0 = time.perf_counter()
            r = client.post("/api/v1/analyst/ask", json={"question": q_text})
            total_ms = (time.perf_counter() - t0) * 1000.0
            assert r.status_code == 200, f"{label} failed with HTTP {r.status_code}: {r.text}"
            data = r.json()
            assert data["row_count"] >= 1, f"{label} returned 0 rows"
            assert check_fn(data), (
                f"{label} did not match Phase 1 ground truth! rows={data['rows']} answer={data['answer']}"
            )
            print(
                f"  [PASS] {label} (HTTP 200 | total={total_ms:.0f} ms | sql={data['execution_ms']:.1f} ms | retries={data['retries_used']} | rows={data['row_count']})",
                flush=True,
            )
            print(f"    SQL:    {data['sql'].replace(chr(10), ' ')}", flush=True)
            print(f"    Answer: {data['answer']}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify AI Analyst security and live Q&A.")
    parser.add_argument(
        "--security-only",
        action="store_true",
        help="Run only offline SQL security, timeout, and mocked retry tests (no LLM calls).",
    )
    args = parser.parse_args()

    settings.warm_cache_on_startup = False
    run_security_and_guardrail_tests()
    if not args.security_only:
        run_live_qa_tests()
    print("\nALL PHASE 5 SECURITY, TIMEOUT & AI ANALYST CHECKS PASSED.", flush=True)


if __name__ == "__main__":
    main()
