"""Exploratory Data Analysis for Farmacia Lumen (data/farmacia.db)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "farmacia.db"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def q(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    return conn.execute(sql, params).fetchall()


def section(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def main() -> None:
    conn = connect()

    # 1. Schema overview: tables, row counts, indexes, FK integrity
    section("1. TABLES, ROW COUNTS, INDEXES & FK INTEGRITY")
    tables = [
        r["name"]
        for r in q(
            conn,
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name",
        )
    ]
    for t in tables:
        cnt = q(conn, f'SELECT COUNT(*) AS c FROM "{t}"')[0]["c"]
        fks = q(conn, f'PRAGMA foreign_key_list("{t}")')
        fk_str = ", ".join(f"{f['from']}->{f['table']}.{f['to']}" for f in fks) or "-"
        print(f"  {t:<16} {cnt:>10,} rows | FKs: {fk_str}")

    idxs = q(
        conn,
        "SELECT name, tbl_name FROM sqlite_master WHERE type='index' AND sql IS NOT NULL",
    )
    print(f"  Explicit secondary indexes: {len(idxs)}")
    fk_violations = q(conn, "PRAGMA foreign_key_check")
    print(f"  PRAGMA foreign_key_check violations: {len(fk_violations)}")

    # 2. Actual Date Ranges
    section("2. ACTUAL MIN/MAX DATE RANGES")
    date_checks = [
        ("bonuri.cand", "SELECT MIN(cand), MAX(cand), COUNT(DISTINCT substr(cand,1,10)) FROM bonuri"),
        ("receptii.data", "SELECT MIN(data), MAX(data), COUNT(DISTINCT data) FROM receptii"),
        ("target_lunar.luna", "SELECT MIN(luna), MAX(luna), COUNT(DISTINCT luna) FROM target_lunar"),
        ("preturi.de_la", "SELECT MIN(de_la), MAX(de_la), COUNT(*) FROM preturi"),
        ("preturi.pana_la (non-null)", "SELECT MIN(pana_la), MAX(pana_la), COUNT(pana_la) FROM preturi"),
        ("oferte.inceput..sfarsit", "SELECT MIN(inceput), MAX(sfarsit), COUNT(*) FROM oferte"),
        ("magazine.deschis_la", "SELECT MIN(deschis_la), MAX(deschis_la), COUNT(*) FROM magazine"),
        ("magazine.inchis_la", "SELECT MIN(inchis_la), MAX(inchis_la), COUNT(inchis_la) FROM magazine"),
        ("clienti.inscris_la", "SELECT MIN(inscris_la), MAX(inscris_la), COUNT(inscris_la) FROM clienti"),
    ]
    for label, sql in date_checks:
        r = q(conn, sql)[0]
        print(f"  {label:<28}: {r[0]} .. {r[1]} (n={r[2]})")

    # 3. Data Quality: Nulls, Duplicates, Pricing & Margin Consistency
    section("3. DATA QUALITY: NULLS, DUPLICATES, PRICING & MARGIN CONSISTENCY")
    null_checks = [
        ("bonuri.id_client IS NULL", "SELECT COUNT(*) FROM bonuri WHERE id_client IS NULL"),
        ("vanzari.id_oferta IS NULL", "SELECT COUNT(*) FROM vanzari WHERE id_oferta IS NULL"),
        ("magazine.inchis_la IS NOT NULL", "SELECT COUNT(*) FROM magazine WHERE inchis_la IS NOT NULL"),
        ("magazine missing lat/lon/sqm/emp", "SELECT COUNT(*) FROM magazine WHERE lat IS NULL OR lon IS NULL OR metri_patrati IS NULL OR nr_angajati IS NULL"),
        ("clienti missing an_nasterii", "SELECT COUNT(*) FROM clienti WHERE an_nasterii IS NULL"),
        ("clienti missing sex", "SELECT COUNT(*) FROM clienti WHERE sex IS NULL"),
        ("clienti missing judet/oras/reg", "SELECT COUNT(*) FROM clienti WHERE judet IS NULL OR oras IS NULL OR id_regiune IS NULL"),
        ("clienti missing inscris_la", "SELECT COUNT(*) FROM clienti WHERE inscris_la IS NULL"),
        ("preturi.pana_la IS NULL (current)", "SELECT COUNT(*) FROM preturi WHERE pana_la IS NULL"),
        ("produse.activ = 0", "SELECT COUNT(*) FROM produse WHERE activ = 0"),
    ]
    for label, sql in null_checks:
        print(f"  {label:<38}: {q(conn, sql)[0][0]:,}")

    dup_checks = [
        ("Duplicate produse.cod_ean", "SELECT COUNT(*) FROM (SELECT cod_ean FROM produse GROUP BY cod_ean HAVING COUNT(*) > 1)"),
        ("Duplicate magazine.nume", "SELECT COUNT(*) FROM (SELECT nume FROM magazine GROUP BY nume HAVING COUNT(*) > 1)"),
        ("Duplicate (id_bon, id_produs) in vanzari", "SELECT COUNT(*) FROM (SELECT id_bon, id_produs FROM vanzari GROUP BY id_bon, id_produs HAVING COUNT(*) > 1)"),
        ("Receipts with 0 vanzari lines", "SELECT COUNT(*) FROM bonuri b LEFT JOIN vanzari v ON v.id_bon = b.id WHERE v.id IS NULL"),
    ]
    for label, sql in dup_checks:
        print(f"  {label:<42}: {q(conn, sql)[0][0]:,}")

    # Formula checks on vanzari
    v_checks = q(
        conn,
        """
        SELECT
            COUNT(*) AS total_rows,
            SUM(CASE WHEN cantitate <= 0 THEN 1 ELSE 0 END) AS nonpos_qty,
            SUM(CASE WHEN pret_unitar_fara_tva <= 0 THEN 1 ELSE 0 END) AS nonpos_price,
            SUM(CASE WHEN reducere < 0 THEN 1 ELSE 0 END) AS neg_disc,
            SUM(CASE WHEN ABS(valoare_fara_tva - (cantitate * pret_unitar_fara_tva - reducere)) > 0.02 THEN 1 ELSE 0 END) AS val_mismatch,
            SUM(CASE WHEN ABS(profit - (valoare_fara_tva - cost)) > 0.02 THEN 1 ELSE 0 END) AS profit_mismatch,
            SUM(CASE WHEN profit < 0 THEN 1 ELSE 0 END) AS neg_profit_rows,
            ROUND(SUM(CASE WHEN profit < 0 THEN profit ELSE 0 END), 2) AS neg_profit_sum,
            SUM(CASE WHEN valoare_fara_tva <= 0 THEN 1 ELSE 0 END) AS nonpos_val,
            ROUND(SUM(valoare_fara_tva), 2) AS total_rev,
            ROUND(SUM(cost), 2) AS total_cost,
            ROUND(SUM(profit), 2) AS total_profit,
            ROUND(SUM(reducere), 2) AS total_disc,
            SUM(cantitate) AS total_units
        FROM vanzari
        """,
    )[0]
    print(f"  Vanzari totals: rev={v_checks['total_rev']:,.2f} RON | cost={v_checks['total_cost']:,.2f} | profit={v_checks['total_profit']:,.2f} ({100*v_checks['total_profit']/v_checks['total_rev']:.2f}%) | disc={v_checks['total_disc']:,.2f} | units={v_checks['total_units']:,}")
    print(f"  Formula checks: val_mismatch={v_checks['val_mismatch']}, profit_mismatch={v_checks['profit_mismatch']}, nonpos_qty={v_checks['nonpos_qty']}, nonpos_val={v_checks['nonpos_val']}, neg_disc={v_checks['neg_disc']}")
    print(f"  Negative profit lines: {v_checks['neg_profit_rows']:,} rows totaling {v_checks['neg_profit_sum']:,.2f} RON")

    # Preturi checks
    p_checks = q(
        conn,
        """
        SELECT
            COUNT(*) AS n,
            SUM(CASE WHEN pret_fara_tva <= cost_achizitie THEN 1 ELSE 0 END) AS inverted_margin,
            ROUND(MIN((pret_fara_tva - cost_achizitie)/pret_fara_tva)*100, 2) AS min_m_pct,
            ROUND(MAX((pret_fara_tva - cost_achizitie)/pret_fara_tva)*100, 2) AS max_m_pct
        FROM preturi
        """,
    )[0]
    print(f"  Preturi: {p_checks['n']} rows | cost>=price: {p_checks['inverted_margin']} | margin range: {p_checks['min_m_pct']}%..{p_checks['max_m_pct']}%")

    # Check if vanzari prices match preturi table
    price_diff = q(
        conn,
        """
        SELECT
            COUNT(*) AS checked,
            SUM(CASE WHEN ABS(v.pret_unitar_fara_tva - p.pret_fara_tva) > 0.02 THEN 1 ELSE 0 END) AS price_mismatch,
            SUM(CASE WHEN ABS(v.cost - v.cantitate * p.cost_achizitie) > 0.02 THEN 1 ELSE 0 END) AS cost_mismatch
        FROM vanzari v
        JOIN bonuri b ON b.id = v.id_bon
        JOIN preturi p ON p.id_produs = v.id_produs
          AND substr(b.cand, 1, 10) >= p.de_la
          AND (p.pana_la IS NULL OR substr(b.cand, 1, 10) <= p.pana_la)
        """,
    )[0]
    print(f"  Vanzari vs Preturi join: matched={price_diff['checked']:,}/{v_checks['total_rows']:,} | price_mismatch={price_diff['price_mismatch']:,} | cost_mismatch={price_diff['cost_mismatch']:,}")

    # 4. Monthly Trends & Seasonality
    section("4. MONTHLY REVENUE, PROFIT, RECEIPTS & TARGET ATTAINMENT")
    monthly = q(
        conn,
        """
        WITH m_sales AS (
            SELECT substr(b.cand, 1, 7) AS luna,
                   COUNT(DISTINCT b.id) AS bonuri,
                   COUNT(DISTINCT b.id_magazin) AS active_stores,
                   SUM(v.cantitate) AS units,
                   ROUND(SUM(v.valoare_fara_tva), 2) AS rev,
                   ROUND(SUM(v.profit), 2) AS profit,
                   ROUND(SUM(v.reducere), 2) AS disc
            FROM bonuri b
            JOIN vanzari v ON v.id_bon = b.id
            GROUP BY 1
        ),
        m_target AS (
            SELECT luna, ROUND(SUM(target_vanzari), 2) AS target, COUNT(*) AS target_stores
            FROM target_lunar
            GROUP BY 1
        )
        SELECT s.luna, s.active_stores, t.target_stores, s.bonuri, s.rev, t.target,
               ROUND(100.0 * s.rev / t.target, 2) AS att_pct,
               ROUND(100.0 * s.profit / s.rev, 2) AS margin_pct,
               ROUND(s.rev / s.bonuri, 2) AS aov
        FROM m_sales s
        LEFT JOIN m_target t ON t.luna = s.luna
        ORDER BY s.luna
        """,
    )
    print(f"  {'Luna':<8} {'St':>2}/{'Tg':<2} {'Bonuri':>8} {'Revenue':>12} {'Target':>12} {'Att%':>7} {'Mgn%':>6} {'AOV':>7}")
    for r in monthly:
        print(f"  {r['luna']:<8} {r['active_stores']:>2}/{r['target_stores'] or 0:<2} {r['bonuri']:>8,} {r['rev']:>12,.2f} {(r['target'] or 0):>12,.2f} {(r['att_pct'] or 0):>6.1f}% {r['margin_pct']:>5.1f}% {r['aov']:>7.2f}")

    # 5. Store-by-store performance, openings/closings, target attainment & sudden drops
    section("5. STORES: PROFILE, LIFESPAN, REVENUE VS TARGET & RECENT TREND")
    stores = q(
        conn,
        """
        WITH s_sales AS (
            SELECT b.id_magazin,
                   MIN(substr(b.cand,1,10)) AS first_sale,
                   MAX(substr(b.cand,1,10)) AS last_sale,
                   COUNT(DISTINCT substr(b.cand,1,7)) AS sale_months,
                   COUNT(DISTINCT b.id) AS bonuri,
                   ROUND(SUM(v.valoare_fara_tva), 2) AS rev,
                   ROUND(SUM(v.profit), 2) AS profit
            FROM bonuri b
            JOIN vanzari v ON v.id_bon = b.id
            GROUP BY b.id_magazin
        ),
        s_target AS (
            SELECT id_magazin, ROUND(SUM(target_vanzari), 2) AS target, COUNT(*) AS target_months
            FROM target_lunar
            GROUP BY id_magazin
        )
        SELECT m.id, m.nume, r.nume AS regiune, m.oras, m.metri_patrati AS sqm, m.nr_angajati AS emp,
               m.deschis_la, m.inchis_la, s.first_sale, s.last_sale, s.sale_months, t.target_months,
               s.rev, t.target,
               ROUND(100.0 * s.rev / t.target, 2) AS att_pct,
               ROUND(100.0 * s.profit / s.rev, 2) AS mgn_pct,
               ROUND(s.rev / s.bonuri, 2) AS aov
        FROM magazine m
        JOIN regiuni r ON r.id = m.id_regiune
        LEFT JOIN s_sales s ON s.id_magazin = m.id
        LEFT JOIN s_target t ON t.id_magazin = m.id
        ORDER BY att_pct ASC
        """,
    )
    print(f"  {'ID':>2} {'Store':<26} {'Regiune':<14} {'Open':<10} {'Close':<10} {'Mo':>2}/{ 'Tg':<2} {'Revenue':>11} {'Target':>11} {'Att%':>6} {'Mgn%':>5}")
    for r in stores:
        print(
            f"  {r['id']:>2} {r['nume'][:26]:<26} {r['regiune'][:14]:<14} {r['deschis_la']:<10} {(r['inchis_la'] or '-'):<10} "
            f"{r['sale_months']:>2}/{r['target_months']:<2} {r['rev']:>11,.0f} {r['target']:>11,.0f} {r['att_pct']:>5.1f}% {r['mgn_pct']:>4.1f}%"
        )

    # Check sharp month-over-month store revenue drops (>25% drop vs trailing 3-month avg)
    section("6. SHARP STORE ANOMALIES (MONTHLY REV VS STORE MEDIAN / PREV 3M)")
    store_monthly = q(
        conn,
        """
        WITH sm AS (
            SELECT b.id_magazin, m.nume, substr(b.cand,1,7) AS luna,
                   ROUND(SUM(v.valoare_fara_tva), 2) AS rev
            FROM bonuri b
            JOIN vanzari v ON v.id_bon = b.id
            JOIN magazine m ON m.id = b.id_magazin
            GROUP BY b.id_magazin, substr(b.cand,1,7)
        ),
        sm_t AS (
            SELECT sm.id_magazin, sm.nume, sm.luna, sm.rev, t.target_vanzari AS target,
                   ROUND(100.0 * sm.rev / t.target_vanzari, 1) AS att_pct,
                   LAG(sm.rev) OVER (PARTITION BY sm.id_magazin ORDER BY sm.luna) AS prev_rev
            FROM sm
            LEFT JOIN target_lunar t ON t.id_magazin = sm.id_magazin AND t.luna = sm.luna
        )
        SELECT id_magazin, nume, luna, rev, prev_rev, target, att_pct,
               ROUND(100.0 * (rev - prev_rev) / prev_rev, 1) AS mom_pct
        FROM sm_t
        WHERE (prev_rev IS NOT NULL AND (rev - prev_rev) / prev_rev < -0.25)
           OR att_pct < 70
           OR att_pct > 135
        ORDER BY id_magazin, luna
        """,
    )
    print(f"  Anomalous store-months (MoM < -25% or Att < 70% or Att > 135%): {len(store_monthly)} rows")
    for r in store_monthly[:40]:
        print(f"    Store {r['id_magazin']:>2} ({r['nume'][:22]:<22}) {r['luna']}: rev={r['rev']:>9,.0f} prev={(r['prev_rev'] or 0):>9,.0f} ({(r['mom_pct'] or 0):>+5.1f}%) | tgt={(r['target'] or 0):>9,.0f} att={(r['att_pct'] or 0):>5.1f}%")
    if len(store_monthly) > 40:
        print(f"    ... ({len(store_monthly) - 40} more)")

    # 7. Categories & Products
    section("7. CATEGORIES & PRODUCTS MIX")
    cats = q(
        conn,
        """
        SELECT c1.id AS l1_id, c1.nume AS l1_nume,
               COUNT(DISTINCT c2.id) AS subcats,
               COUNT(DISTINCT p.id) AS prods,
               ROUND(SUM(v.valoare_fara_tva), 2) AS rev,
               ROUND(SUM(v.profit), 2) AS profit,
               ROUND(100.0 * SUM(v.profit) / SUM(v.valoare_fara_tva), 2) AS mgn_pct,
               SUM(v.cantitate) AS units
        FROM categorii c1
        LEFT JOIN categorii c2 ON c2.id_parinte = c1.id
        LEFT JOIN produse p ON p.id_categorie = c2.id OR p.id_categorie = c1.id
        LEFT JOIN vanzari v ON v.id_produs = p.id
        WHERE c1.id_parinte IS NULL
        GROUP BY c1.id
        ORDER BY rev DESC
        """,
    )
    # Check max depth of categorii
    max_depth = q(
        conn,
        """
        SELECT COUNT(*) AS l1,
               (SELECT COUNT(*) FROM categorii WHERE id_parinte IN (SELECT id FROM categorii WHERE id_parinte IS NULL)) AS l2,
               (SELECT COUNT(*) FROM categorii WHERE id_parinte NOT IN (SELECT id FROM categorii WHERE id_parinte IS NULL) AND id_parinte IS NOT NULL) AS l3_plus
        FROM categorii WHERE id_parinte IS NULL
        """,
    )[0]
    print(f"  Category hierarchy: L1={max_depth['l1']}, L2={max_depth['l2']}, L3+={max_depth['l3_plus']}")
    prods_on_l1 = q(conn, "SELECT COUNT(*) FROM produse p JOIN categorii c ON c.id = p.id_categorie WHERE c.id_parinte IS NULL")[0][0]
    print(f"  Products attached directly to L1: {prods_on_l1}")
    for r in cats:
        print(f"    [{r['l1_id']:>2}] {r['l1_nume']:<26} sub={r['subcats']:>2} prods={r['prods']:>3} | rev={(r['rev'] or 0):>12,.2f} | mgn={(r['mgn_pct'] or 0):>5.1f}% | units={(r['units'] or 0):>8,}")

    # 8. Promotions (Oferte)
    section("8. PROMOTIONS (OFERTE) EFFECTIVENESS & NEGATIVE MARGINS")
    promos = q(
        conn,
        """
        SELECT o.id, o.nume, o.tip, o.valoare, o.inceput, o.sfarsit,
               (SELECT COUNT(*) FROM oferte_produse op WHERE op.id_oferta = o.id) AS n_prods,
               COUNT(v.id) AS lines,
               SUM(v.cantitate) AS units,
               ROUND(SUM(v.valoare_fara_tva), 2) AS rev,
               ROUND(SUM(v.reducere), 2) AS disc,
               ROUND(SUM(v.profit), 2) AS profit,
               ROUND(100.0 * SUM(v.profit) / NULLIF(SUM(v.valoare_fara_tva), 0), 2) AS mgn_pct,
               SUM(CASE WHEN v.profit < 0 THEN 1 ELSE 0 END) AS neg_lines
        FROM oferte o
        LEFT JOIN vanzari v ON v.id_oferta = o.id
        GROUP BY o.id
        ORDER BY o.inceput, o.id
        """,
    )
    print(f"  Total promotions: {len(promos)}")
    print(f"  {'ID':>2} {'Name':<28} {'Tip':<7} {'Val':>5} {'Window':<21} {'Pr':>3} {'Rev':>11} {'Disc':>10} {'Profit':>10} {'Mgn%':>6} {'NegL':>6}")
    for r in promos:
        win = f"{r['inceput']}..{r['sfarsit'][5:]}"
        print(
            f"  {r['id']:>2} {r['nume'][:28]:<28} {r['tip']:<7} {r['valoare']:>5.1f} {win:<21} {r['n_prods']:>3} "
            f"{(r['rev'] or 0):>11,.0f} {(r['disc'] or 0):>10,.0f} {(r['profit'] or 0):>10,.0f} {(r['mgn_pct'] or 0):>5.1f}% {(r['neg_lines'] or 0):>6,}"
        )

    # Breakdown of negative profit lines: promo vs non-promo
    neg_break = q(
        conn,
        """
        SELECT CASE WHEN id_oferta IS NULL THEN 'No Promo' ELSE 'Promo' END AS grp,
               COUNT(*) AS lines,
               ROUND(SUM(valoare_fara_tva), 2) AS rev,
               ROUND(SUM(profit), 2) AS profit
        FROM vanzari
        WHERE profit < 0
        GROUP BY 1
        """,
    )
    print("  Negative-profit lines breakdown:", [dict(r) for r in neg_break])

    # Check if promo applied outside window or outside oferte_produse
    promo_anoms = q(
        conn,
        """
        SELECT
            SUM(CASE WHEN substr(b.cand,1,10) < o.inceput OR substr(b.cand,1,10) > o.sfarsit THEN 1 ELSE 0 END) AS out_of_window,
            SUM(CASE WHEN op.id_produs IS NULL THEN 1 ELSE 0 END) AS not_in_op
        FROM vanzari v
        JOIN bonuri b ON b.id = v.id_bon
        JOIN oferte o ON o.id = v.id_oferta
        LEFT JOIN oferte_produse op ON op.id_oferta = v.id_oferta AND op.id_produs = v.id_produs
        WHERE v.id_oferta IS NOT NULL
        """,
    )[0]
    print(f"  Promo integrity: out_of_window={promo_anoms['out_of_window']}, not_in_oferte_produse={promo_anoms['not_in_op']}")

    # 9. Inventory (magazin_stoc) & Receptions (receptii)
    section("9. INVENTORY, STOCKOUTS, DEAD STOCK, RECEPTIONS & LEDGER RECONCILIATION")
    stoc_summary = q(
        conn,
        """
        SELECT COUNT(*) AS total_pairs,
               SUM(CASE WHEN stoc < 0 THEN 1 ELSE 0 END) AS neg_stoc,
               SUM(CASE WHEN stoc = 0 THEN 1 ELSE 0 END) AS zero_stoc,
               SUM(CASE WHEN stoc BETWEEN 1 AND 5 THEN 1 ELSE 0 END) AS low_stoc_1_5,
               SUM(stoc) AS total_units,
               MIN(stoc) AS min_stoc,
               MAX(stoc) AS max_stoc
        FROM magazin_stoc
        """,
    )[0]
    print("  magazin_stoc summary:", dict(stoc_summary))

    # Ledger reconciliation: receptii - vanzari vs magazin_stoc
    recon = q(
        conn,
        """
        WITH rec AS (
            SELECT id_magazin, id_produs, SUM(cantitate) AS qty_in
            FROM receptii
            GROUP BY id_magazin, id_produs
        ),
        sold AS (
            SELECT b.id_magazin, v.id_produs, SUM(v.cantitate) AS qty_out
            FROM bonuri b
            JOIN vanzari v ON v.id_bon = b.id
            GROUP BY b.id_magazin, v.id_produs
        )
        SELECT COUNT(*) AS pairs,
               SUM(CASE WHEN ms.stoc != COALESCE(r.qty_in, 0) - COALESCE(s.qty_out, 0) THEN 1 ELSE 0 END) AS diff_pairs,
               SUM(ms.stoc - (COALESCE(r.qty_in, 0) - COALESCE(s.qty_out, 0))) AS net_unit_diff,
               SUM(ABS(ms.stoc - (COALESCE(r.qty_in, 0) - COALESCE(s.qty_out, 0)))) AS abs_unit_diff
        FROM magazin_stoc ms
        LEFT JOIN rec r ON r.id_magazin = ms.id_magazin AND r.id_produs = ms.id_produs
        LEFT JOIN sold s ON s.id_magazin = ms.id_magazin AND s.id_produs = ms.id_produs
        """,
    )[0]
    print("  Ledger reconciliation (stoc vs receptii - vanzari):", dict(recon))

    # Receptions breakdown by tip and monthly
    rec_tip = q(
        conn,
        "SELECT tip, COUNT(*) AS n, SUM(cantitate) AS qty, MIN(cantitate) AS min_q, MAX(cantitate) AS max_q, MIN(data) AS d_min, MAX(data) AS d_max FROM receptii GROUP BY tip",
    )
    for r in rec_tip:
        print("  Receptii tip:", dict(r))

    # Store-level stockout counts (zero stock on active products that had sales in last 90 days)
    stockouts = q(
        conn,
        """
        WITH recent_sales AS (
            SELECT b.id_magazin, v.id_produs, SUM(v.cantitate) AS qty_90d, ROUND(SUM(v.valoare_fara_tva), 2) AS rev_90d
            FROM bonuri b
            JOIN vanzari v ON v.id_bon = b.id
            WHERE b.cand >= '2026-08-01'
            GROUP BY b.id_magazin, v.id_produs
        )
        SELECT m.id, m.nume, m.inchis_la,
               COUNT(*) AS total_skus,
               SUM(CASE WHEN ms.stoc = 0 THEN 1 ELSE 0 END) AS zero_skus,
               SUM(CASE WHEN ms.stoc = 0 AND COALESCE(rs.qty_90d, 0) >= 10 THEN 1 ELSE 0 END) AS high_vel_stockouts,
               ROUND(SUM(CASE WHEN ms.stoc = 0 THEN COALESCE(rs.rev_90d, 0) ELSE 0 END), 2) AS rev_90d_on_zero_skus
        FROM magazin_stoc ms
        JOIN magazine m ON m.id = ms.id_magazin
        JOIN produse p ON p.id = ms.id_produs
        LEFT JOIN recent_sales rs ON rs.id_magazin = ms.id_magazin AND rs.id_produs = ms.id_produs
        WHERE p.activ = 1
        GROUP BY m.id
        ORDER BY zero_skus DESC
        """,
    )
    print("\n  Top 10 stores by zero-stock active SKUs (sales >= 2026-08-01):")
    for r in stockouts[:10]:
        print(f"    Store {r['id']:>2} ({r['nume'][:24]:<24}) closed={r['inchis_la'] or '-':<10} zero={r['zero_skus']:>3}/{r['total_skus']} | hi_vel_zero={r['high_vel_stockouts']:>3} | 90d_rev_at_risk={r['rev_90d_on_zero_skus']:>10,.2f}")

    # Dead stock: stoc > 0, zero sales in last 90 or 180 days, value at current cost_achizitie
    dead_stock = q(
        conn,
        """
        WITH curr_price AS (
            SELECT id_produs, cost_achizitie, pret_fara_tva FROM preturi WHERE pana_la IS NULL
        ),
        sales_90 AS (
            SELECT b.id_magazin, v.id_produs, SUM(v.cantitate) AS q90
            FROM bonuri b JOIN vanzari v ON v.id_bon = b.id
            WHERE b.cand >= '2026-08-01'
            GROUP BY b.id_magazin, v.id_produs
        ),
        sales_all AS (
            SELECT b.id_magazin, v.id_produs, SUM(v.cantitate) AS q_all
            FROM bonuri b JOIN vanzari v ON v.id_bon = b.id
            GROUP BY b.id_magazin, v.id_produs
        )
        SELECT
            SUM(CASE WHEN ms.stoc > 0 AND COALESCE(s90.q90, 0) = 0 THEN 1 ELSE 0 END) AS dead90_pairs,
            SUM(CASE WHEN ms.stoc > 0 AND COALESCE(s90.q90, 0) = 0 THEN ms.stoc ELSE 0 END) AS dead90_units,
            ROUND(SUM(CASE WHEN ms.stoc > 0 AND COALESCE(s90.q90, 0) = 0 THEN ms.stoc * cp.cost_achizitie ELSE 0 END), 2) AS dead90_cost_ron,
            SUM(CASE WHEN ms.stoc > 0 AND COALESCE(sa.q_all, 0) = 0 THEN 1 ELSE 0 END) AS never_sold_pairs,
            ROUND(SUM(CASE WHEN ms.stoc > 0 AND COALESCE(sa.q_all, 0) = 0 THEN ms.stoc * cp.cost_achizitie ELSE 0 END), 2) AS never_sold_cost_ron,
            ROUND(SUM(ms.stoc * cp.cost_achizitie), 2) AS total_inv_cost_ron,
            SUM(CASE WHEN ms.stoc > 0 AND p.activ = 0 THEN ms.stoc ELSE 0 END) AS inactive_stoc_units,
            ROUND(SUM(CASE WHEN ms.stoc > 0 AND p.activ = 0 THEN ms.stoc * cp.cost_achizitie ELSE 0 END), 2) AS inactive_stoc_cost_ron
        FROM magazin_stoc ms
        JOIN magazine m ON m.id = ms.id_magazin
        JOIN produse p ON p.id = ms.id_produs
        JOIN curr_price cp ON cp.id_produs = ms.id_produs
        LEFT JOIN sales_90 s90 ON s90.id_magazin = ms.id_magazin AND s90.id_produs = ms.id_produs
        LEFT JOIN sales_all sa ON sa.id_magazin = ms.id_magazin AND sa.id_produs = ms.id_produs
        WHERE m.inchis_la IS NULL
        """,
    )[0]
    print("  Dead stock (open stores only):", dict(dead_stock))

    # Closed store remaining stock
    closed_stoc = q(
        conn,
        """
        SELECT m.id, m.nume, m.inchis_la, SUM(ms.stoc) AS units,
               ROUND(SUM(ms.stoc * p.cost_achizitie), 2) AS cost_ron
        FROM magazin_stoc ms
        JOIN magazine m ON m.id = ms.id_magazin
        JOIN preturi p ON p.id_produs = ms.id_produs AND p.pana_la IS NULL
        WHERE m.inchis_la IS NOT NULL
        GROUP BY m.id
        """,
    )
    print("  Closed stores remaining stock:", [dict(r) for r in closed_stoc])

    # 10. Customers (clienti)
    section("10. CUSTOMERS & LOYALTY INSIGHTS")
    cust_pen = q(
        conn,
        """
        SELECT CASE WHEN b.id_client IS NULL THEN 'No Card' ELSE 'Loyalty Card' END AS seg,
               COUNT(DISTINCT b.id) AS bonuri,
               ROUND(SUM(v.valoare_fara_tva), 2) AS rev,
               ROUND(SUM(v.valoare_fara_tva) / COUNT(DISTINCT b.id), 2) AS aov,
               ROUND(100.0 * SUM(v.profit) / SUM(v.valoare_fara_tva), 2) AS mgn_pct
        FROM bonuri b
        JOIN vanzari v ON v.id_bon = b.id
        GROUP BY 1
        """,
    )
    for r in cust_pen:
        print(" ", dict(r))

    cust_freq = q(
        conn,
        """
        WITH cf AS (
            SELECT c.id, COUNT(DISTINCT b.id) AS visits, ROUND(SUM(v.valoare_fara_tva), 2) AS spend
            FROM clienti c
            LEFT JOIN bonuri b ON b.id_client = c.id
            LEFT JOIN vanzari v ON v.id_bon = b.id
            GROUP BY c.id
        )
        SELECT
            COUNT(*) AS total_clients,
            SUM(CASE WHEN visits = 0 THEN 1 ELSE 0 END) AS zero_visits,
            SUM(CASE WHEN visits = 1 THEN 1 ELSE 0 END) AS one_visit,
            SUM(CASE WHEN visits BETWEEN 2 AND 5 THEN 1 ELSE 0 END) AS v_2_5,
            SUM(CASE WHEN visits BETWEEN 6 AND 20 THEN 1 ELSE 0 END) AS v_6_20,
            SUM(CASE WHEN visits > 20 THEN 1 ELSE 0 END) AS v_gt_20,
            MAX(visits) AS max_visits,
            MAX(spend) AS max_spend
        FROM cf
        """,
    )[0]
    print("  Customer frequency:", dict(cust_freq))

    # 11. Deep-Dive Verification of Planted Anomalies & Business Patterns
    section("11. DEEP-DIVE ANOMALIES: STORES, RETURNS, PROMOS, SUPPLY & PRICES")

    print("  [11a] Returns (cantitate <= 0) & mismatch explanation:")
    ret = q(
        conn,
        """
        SELECT COUNT(*) AS lines, MIN(cantitate) AS min_q, MAX(cantitate) AS max_q,
               ROUND(SUM(valoare_fara_tva), 2) AS rev, ROUND(SUM(profit), 2) AS prof,
               SUM(CASE WHEN id_oferta IS NOT NULL THEN 1 ELSE 0 END) AS with_promo
        FROM vanzari WHERE cantitate <= 0
        """,
    )[0]
    print("   ", dict(ret))
    pos_neg = q(
        conn,
        """
        SELECT CASE WHEN id_oferta IS NULL THEN 'No Promo' ELSE 'Promo' END AS grp,
               COUNT(*) AS lines, ROUND(SUM(valoare_fara_tva), 2) AS rev, ROUND(SUM(profit), 2) AS prof
        FROM vanzari WHERE cantitate > 0 AND profit < 0 GROUP BY 1
        """,
    )
    print("    Positive-qty negative-profit lines:", [dict(r) for r in pos_neg])

    print("\n  [11b] Store 9 (Constanța Tomis Nord) vs Store 10 (Constanța Centru) monthly:")
    for r in q(
        conn,
        """
        SELECT substr(b.cand,1,7) AS luna,
               ROUND(SUM(CASE WHEN b.id_magazin=9 THEN v.valoare_fara_tva ELSE 0 END), 0) AS s9_rev,
               (SELECT target_vanzari FROM target_lunar WHERE id_magazin=9 AND luna=substr(b.cand,1,7)) AS s9_tgt,
               COUNT(DISTINCT CASE WHEN b.id_magazin=9 THEN b.id END) AS s9_bon,
               ROUND(SUM(CASE WHEN b.id_magazin=10 THEN v.valoare_fara_tva ELSE 0 END), 0) AS s10_rev,
               (SELECT target_vanzari FROM target_lunar WHERE id_magazin=10 AND luna=substr(b.cand,1,7)) AS s10_tgt
        FROM bonuri b JOIN vanzari v ON v.id_bon=b.id
        WHERE b.id_magazin IN (9, 10)
        GROUP BY 1 ORDER BY 1
        """,
    ):
        a9 = 100 * r["s9_rev"] / r["s9_tgt"]
        a10 = 100 * r["s10_rev"] / r["s10_tgt"]
        print(f"    {r['luna']}: S9={r['s9_rev']:>7,.0f}/{r['s9_tgt']:>7,.0f} ({a9:5.1f}%, {r['s9_bon']:>4} bon) | S10={r['s10_rev']:>7,.0f}/{r['s10_tgt']:>7,.0f} ({a10:5.1f}%)")

    print("\n  [11c] Store 11 (Galați) August 2025 outage & chain closed days:")
    s11_days = [r["d"] for r in q(conn, "SELECT DISTINCT substr(cand,1,10) AS d FROM bonuri WHERE id_magazin=11 AND cand LIKE '2025-08%' ORDER BY 1")]
    print(f"    Store 11 active days in 2025-08 ({len(s11_days)} days): {s11_days}")
    # Check any store with >3 consecutive missing days inside its open window
    print("    Store-level missing-day gaps (>3 days within open period):")
    for m in q(conn, "SELECT id, nume, deschis_la, inchis_la FROM magazine ORDER BY id"):
        days = [r["d"] for r in q(conn, "SELECT DISTINCT substr(cand,1,10) AS d FROM bonuri WHERE id_magazin=? ORDER BY 1", (m["id"],))]
        gaps = []
        from datetime import date
        for i in range(1, len(days)):
            d1 = date.fromisoformat(days[i - 1])
            d2 = date.fromisoformat(days[i])
            diff = (d2 - d1).days - 1
            if diff >= 3:
                gaps.append((days[i - 1], days[i], diff))
        if gaps:
            print(f"      Store {m['id']:>2} ({m['nume']}): {gaps}")

    print("\n  [11d] Cluj cannibalization check: Store 17 (Cluj Centru) vs Store 18 (Cluj Mărăști, opened 2026-03-16):")
    for r in q(
        conn,
        """
        SELECT substr(b.cand,1,7) AS luna,
               ROUND(SUM(CASE WHEN b.id_magazin=17 THEN v.valoare_fara_tva ELSE 0 END), 0) AS s17_rev,
               (SELECT target_vanzari FROM target_lunar WHERE id_magazin=17 AND luna=substr(b.cand,1,7)) AS s17_tgt,
               ROUND(SUM(CASE WHEN b.id_magazin=18 THEN v.valoare_fara_tva ELSE 0 END), 0) AS s18_rev,
               (SELECT target_vanzari FROM target_lunar WHERE id_magazin=18 AND luna=substr(b.cand,1,7)) AS s18_tgt
        FROM bonuri b JOIN vanzari v ON v.id_bon=b.id
        WHERE b.id_magazin IN (17, 18)
        GROUP BY 1 ORDER BY 1
        """,
    ):
        a17 = 100 * r["s17_rev"] / r["s17_tgt"]
        a18 = (100 * r["s18_rev"] / r["s18_tgt"]) if r["s18_tgt"] else 0
        print(f"    {r['luna']}: ClujCentru={r['s17_rev']:>7,.0f}/{r['s17_tgt']:>7,.0f} ({a17:5.1f}%) | ClujMarasti={r['s18_rev']:>7,.0f}/{r['s18_tgt'] or 0:>7,.0f} ({a18:5.1f}%)")

    print("\n  [11e] Store 16 (Deva, closed 2026-06-30) transfers:")
    for r in q(
        conn,
        """
        SELECT m.id, m.nume, COUNT(*) AS skus, SUM(r.cantitate) AS qty
        FROM receptii r JOIN magazine m ON m.id=r.id_magazin
        WHERE r.tip='transfer' GROUP BY 1 ORDER BY qty
        """,
    ):
        print("   ", dict(r))

    print("\n  [11f] Promo uplift (daily rev & profit during promo vs 28 days prior on promo SKUs):")
    for r in q(
        conn,
        """
        SELECT o.id, o.nume, o.tip, o.valoare,
               CAST(julianday(o.sfarsit) - julianday(o.inceput) + 1 AS INT) AS days,
               ROUND(SUM(CASE WHEN substr(b.cand,1,10) BETWEEN o.inceput AND o.sfarsit THEN v.valoare_fara_tva ELSE 0 END), 0) AS rev_dur,
               ROUND(SUM(CASE WHEN substr(b.cand,1,10) BETWEEN o.inceput AND o.sfarsit THEN v.profit ELSE 0 END), 0) AS prof_dur,
               ROUND(SUM(CASE WHEN substr(b.cand,1,10) BETWEEN date(o.inceput, '-28 days') AND date(o.inceput, '-1 day') THEN v.valoare_fara_tva ELSE 0 END), 0) AS rev_pre,
               ROUND(SUM(CASE WHEN substr(b.cand,1,10) BETWEEN date(o.inceput, '-28 days') AND date(o.inceput, '-1 day') THEN v.profit ELSE 0 END), 0) AS prof_pre
        FROM oferte o
        JOIN oferte_produse op ON op.id_oferta = o.id
        JOIN vanzari v ON v.id_produs = op.id_produs
        JOIN bonuri b ON b.id = v.id_bon
        WHERE substr(b.cand,1,10) BETWEEN date(o.inceput, '-28 days') AND o.sfarsit
        GROUP BY o.id ORDER BY o.inceput
        """,
    ):
        rd, rp = r["rev_dur"] / r["days"], r["rev_pre"] / 28.0
        pd, pp = r["prof_dur"] / r["days"], r["prof_pre"] / 28.0
        ru = 100 * (rd - rp) / rp if rp else 0
        pu = 100 * (pd - pp) / pp if pp else 0
        print(f"    P{r['id']:>2} {r['nume'][:26]:<26} ({r['days']:>2}d): rev/d {rd:>7,.0f} vs {rp:>7,.0f} ({ru:>+6.1f}%) | prof/d {pd:>6,.0f} vs {pp:>6,.0f} ({pu:>+6.1f}%)")

    print("\n  [11g] Products with highest return rate & abnormal monthly sales drops:")
    for r in q(
        conn,
        """
        SELECT p.id, p.nume, p.brand, p.activ,
               SUM(CASE WHEN v.cantitate > 0 THEN v.cantitate ELSE 0 END) AS sold_q,
               SUM(CASE WHEN v.cantitate < 0 THEN -v.cantitate ELSE 0 END) AS ret_q,
               ROUND(100.0 * SUM(CASE WHEN v.cantitate < 0 THEN -v.cantitate ELSE 0 END) / NULLIF(SUM(CASE WHEN v.cantitate > 0 THEN v.cantitate ELSE 0 END),0), 2) AS ret_pct
        FROM vanzari v JOIN produse p ON p.id=v.id_produs
        GROUP BY p.id ORDER BY ret_pct DESC LIMIT 8
        """,
    ):
        print("   ", dict(r))

    print("\n  [11h] Products with missing sales months or severe monthly drop (<25% of avg):")
    for r in q(
        conn,
        """
        WITH mp AS (
            SELECT v.id_produs, substr(b.cand,1,7) AS luna, SUM(v.cantitate) AS qty
            FROM vanzari v JOIN bonuri b ON b.id=v.id_bon GROUP BY 1,2
        ),
        st AS (
            SELECT id_produs, COUNT(*) AS mos, MIN(qty) AS min_q, MAX(qty) AS max_q, ROUND(AVG(qty),1) AS avg_q
            FROM mp GROUP BY 1
        )
        SELECT p.id, p.nume, p.brand, p.activ, st.mos, st.min_q, st.avg_q, st.max_q
        FROM st JOIN produse p ON p.id=st.id_produs
        WHERE st.mos < 18 OR st.min_q < st.avg_q * 0.2
        ORDER BY st.mos ASC, (1.0*st.min_q/st.avg_q) ASC LIMIT 12
        """,
    ):
        print("   ", dict(r))

    print("\n  [11i] Price changes over time (preturi) & VAT rates (cota_tva):")
    print("    VAT rates:", [dict(r) for r in q(conn, "SELECT cota_tva, COUNT(*) AS n_prods FROM produse GROUP BY 1 ORDER BY 1")])
    for r in q(
        conn,
        """
        WITH pc AS (
            SELECT p1.id_produs, p2.de_la AS d2,
                   ROUND(100.0*(p2.pret_fara_tva - p1.pret_fara_tva)/p1.pret_fara_tva, 1) AS pr_chg,
                   ROUND(100.0*(p2.cost_achizitie - p1.cost_achizitie)/p1.cost_achizitie, 1) AS c_chg
            FROM preturi p1 JOIN preturi p2 ON p2.id_produs=p1.id_produs AND p2.de_la = date(p1.pana_la, '+1 day')
        )
        SELECT substr(d2,1,7) AS luna, COUNT(*) AS n,
               ROUND(AVG(pr_chg),1) AS avg_pr, ROUND(AVG(c_chg),1) AS avg_cost,
               MIN(pr_chg) AS min_pr, MAX(pr_chg) AS max_pr
        FROM pc GROUP BY 1 ORDER BY 1
        """,
    ):
        print("   ", dict(r))

    print("\n  [11j] Regional summary:")
    for r in q(
        conn,
        """
        WITH r_s AS (
            SELECT m.id_regiune, COUNT(DISTINCT m.id) AS stores, ROUND(SUM(v.valoare_fara_tva),2) AS rev, ROUND(SUM(v.profit),2) AS prof
            FROM bonuri b JOIN vanzari v ON v.id_bon=b.id JOIN magazine m ON m.id=b.id_magazin GROUP BY 1
        ),
        r_t AS (
            SELECT m.id_regiune, ROUND(SUM(t.target_vanzari),2) AS tgt
            FROM target_lunar t JOIN magazine m ON m.id=t.id_magazin GROUP BY 1
        )
        SELECT r.id, r.nume, s.stores, s.rev, t.tgt, ROUND(100.0*s.rev/t.tgt,2) AS att_pct, ROUND(100.0*s.prof/s.rev,2) AS mgn_pct
        FROM regiuni r JOIN r_s s ON s.id_regiune=r.id JOIN r_t t ON t.id_regiune=r.id
        ORDER BY att_pct ASC
        """,
    ):
        print("   ", dict(r))


if __name__ == "__main__":
    main()
