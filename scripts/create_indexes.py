"""Idempotent analytical index creation and query latency benchmarks for Farmacia Lumen."""

from __future__ import annotations

import argparse
import sqlite3
import time
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "farmacia.db"

INDEX_DDL: list[str] = [
    """
    CREATE INDEX IF NOT EXISTS idx_bonuri_cand_magazin_client
        ON bonuri(cand, id_magazin, id_client)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_bonuri_magazin_cand
        ON bonuri(id_magazin, cand)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_bonuri_client_cand
        ON bonuri(id_client, cand)
        WHERE id_client IS NOT NULL
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_vanzari_bon_produs
        ON vanzari(id_bon, id_produs, id_oferta, cantitate, valoare_fara_tva, reducere, cost, profit)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_vanzari_produs_bon
        ON vanzari(id_produs, id_bon, cantitate, valoare_fara_tva, reducere, cost, profit, id_oferta)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_vanzari_oferta
        ON vanzari(id_oferta, id_bon, id_produs, cantitate, valoare_fara_tva, reducere, cost, profit)
        WHERE id_oferta IS NOT NULL
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_receptii_magazin_data_tip
        ON receptii(id_magazin, data, tip, cantitate)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_receptii_tip_data
        ON receptii(tip, data)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_produse_categorie_activ
        ON produse(id_categorie, activ)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_preturi_produs_pana_la
        ON preturi(id_produs, pana_la)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_magazine_regiune_inchis
        ON magazine(id_regiune, inchis_la)
    """,
]

BENCHMARK_QUERIES: list[tuple[str, str, tuple]] = [
    (
        "1. Filtered Overview KPIs (2026, Sud-Est)",
        """
        SELECT COUNT(DISTINCT b.id) AS receipts,
               ROUND(SUM(v.valoare_fara_tva), 2) AS net_rev,
               ROUND(SUM(v.profit), 2) AS profit
        FROM bonuri b
        JOIN vanzari v ON v.id_bon = b.id
        JOIN magazine m ON m.id = b.id_magazin
        WHERE b.cand >= ? AND b.cand < ? AND m.id_regiune = ?
        """,
        ("2026-01-01 00:00:00", "2026-11-01 00:00:00", 3),
    ),
    (
        "2. Full 18M Chain Overview KPIs (674k rows)",
        """
        SELECT COUNT(DISTINCT b.id) AS receipts,
               ROUND(SUM(v.valoare_fara_tva), 2) AS net_rev,
               ROUND(SUM(v.profit), 2) AS profit
        FROM bonuri b
        JOIN vanzari v ON v.id_bon = b.id
        WHERE b.cand >= ? AND b.cand < ?
        """,
        ("2025-05-01 00:00:00", "2026-11-01 00:00:00"),
    ),
    (
        "3. Store #9 Monthly Revenue vs Target",
        """
        SELECT substr(b.cand, 1, 7) AS luna,
               COUNT(DISTINCT b.id) AS receipts,
               ROUND(SUM(v.valoare_fara_tva), 2) AS rev
        FROM bonuri b
        JOIN vanzari v ON v.id_bon = b.id
        WHERE b.id_magazin = ? AND b.cand >= ? AND b.cand < ?
        GROUP BY 1
        ORDER BY 1
        """,
        (9, "2025-05-01 00:00:00", "2026-11-01 00:00:00"),
    ),
    (
        "4. L1 Category (id=11) Filtered Revenue",
        """
        SELECT p.id_categorie,
               ROUND(SUM(v.valoare_fara_tva), 2) AS rev,
               ROUND(SUM(v.profit), 2) AS profit
        FROM vanzari v
        JOIN produse p ON p.id = v.id_produs
        WHERE p.id_categorie IN (
            SELECT id FROM categorii WHERE id = ? OR id_parinte = ?
        )
        GROUP BY p.id_categorie
        """,
        (11, 11),
    ),
    (
        "5. Promotions Direct Metrics (excl test)",
        """
        SELECT o.id, o.nume,
               ROUND(SUM(v.valoare_fara_tva), 2) AS rev,
               ROUND(SUM(v.profit), 2) AS profit,
               SUM(CASE WHEN v.cantitate > 0 AND v.profit < 0 THEN 1 ELSE 0 END) AS below_cost
        FROM oferte o
        JOIN vanzari v ON v.id_oferta = o.id
        WHERE o.id != 13
        GROUP BY o.id
        """,
        (),
    ),
    (
        "6. Inventory 90d Stockout Queue",
        """
        WITH vel AS (
            SELECT b.id_magazin, v.id_produs,
                   SUM(v.cantitate) AS qty_90d,
                   ROUND(SUM(v.valoare_fara_tva), 2) AS rev_90d
            FROM bonuri b
            JOIN vanzari v ON v.id_bon = b.id
            WHERE b.cand >= ? AND b.cand < ?
            GROUP BY b.id_magazin, v.id_produs
        )
        SELECT ms.id_magazin, ms.id_produs, COALESCE(vel.rev_90d, 0) AS rev_at_risk
        FROM magazin_stoc ms
        JOIN magazine m ON m.id = ms.id_magazin
        JOIN produse p ON p.id = ms.id_produs
        LEFT JOIN vel ON vel.id_magazin = ms.id_magazin AND vel.id_produs = ms.id_produs
        WHERE m.inchis_la IS NULL AND p.activ = 1 AND ms.stoc = 0
        ORDER BY rev_at_risk DESC
        LIMIT 50
        """,
        ("2026-08-03 00:00:00", "2026-11-01 00:00:00"),
    ),
]


def create_indexes(db_path: Path) -> None:
    """Create analytical indexes and refresh SQLite query planner statistics."""
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")
    conn = sqlite3.connect(str(db_path))
    try:
        for stmt in INDEX_DDL:
            conn.execute(stmt)
        conn.execute("ANALYZE")
        conn.commit()
    finally:
        conn.close()


def run_benchmarks(db_path: Path) -> list[dict[str, object]]:
    """Run timed benchmark queries against the read-only SQLite URI connection."""
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    try:
        conn.execute("PRAGMA cache_size = -64000")
        conn.execute("PRAGMA temp_store = MEMORY")
        conn.execute("PRAGMA mmap_size = 268435456")
        conn.execute("PRAGMA query_only = ON")

        # Warm page cache / mmap once before timing.
        for _, sql, params in BENCHMARK_QUERIES:
            conn.execute(sql, params).fetchall()

        results: list[dict[str, object]] = []
        for label, sql, params in BENCHMARK_QUERIES:
            t0 = time.perf_counter()
            rows = conn.execute(sql, params).fetchall()
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            results.append({"query": label, "ms": round(elapsed_ms, 2), "rows": len(rows)})
        return results
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create analytical SQLite indexes and benchmark.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to farmacia.db")
    parser.add_argument("--skip-bench", action="store_true", help="Skip benchmark timing run")
    args = parser.parse_args()

    t0 = time.perf_counter()
    create_indexes(args.db)
    build_ms = (time.perf_counter() - t0) * 1000.0
    print(f"Analytical indexes verified/created and ANALYZE completed in {build_ms:.1f} ms on {args.db}")

    if not args.skip_bench:
        print("\nBenchmark timings (read-only URI mode, warm cache):")
        for item in run_benchmarks(args.db):
            print(f"  {item['query']:<45} {item['ms']:>7.2f} ms  ({item['rows']} rows)")


if __name__ == "__main__":
    main()
