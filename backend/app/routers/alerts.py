"""Dynamic, SQL-grounded Operational Problems & Recommended Actions Feed."""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query

from ..config import settings
from ..db import get_db, query_all, query_one
from ..schemas import AlertCounts, AlertItem, AlertsResponse
from ..services.filters import (
    GlobalFilters,
    build_sales_where,
    compute_targets,
    get_global_filters,
    sales_joins_sql,
)
from .inventory import get_inventory
from .promotions import get_promotions
from .stores import get_stores

router = APIRouter(tags=["alerts"])

SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


@router.get("/alerts", response_model=AlertsResponse)
def get_alerts(
    severity: Literal["critical", "high", "medium", "low"] | None = Query(default=None),
    category: Literal[
        "store_performance", "promotions", "inventory", "loyalty", "data_hygiene"
    ]
    | None = Query(default=None),
    filters: GlobalFilters = Depends(get_global_filters),
    conn: sqlite3.Connection = Depends(get_db),
) -> AlertsResponse:
    alerts: list[AlertItem] = []

    stores_data = get_stores(sort_by="attainment_pct", filters=filters, conn=conn)
    promos_data = get_promotions(filters=filters, conn=conn)
    inv_data = get_inventory(low_stock_max=5, limit=25, filters=filters, conn=conn)

    # 1. Sustained Store Underperformance (Critical)
    total_chain_shortfall = sum(
        min(0.0, s.variance_ron) for s in stores_data.stores if s.variance_ron is not None
    )
    for st in stores_data.stores:
        if (
            stores_data.target_available
            and st.attainment_pct is not None
            and st.attainment_pct < 82.0
            and st.variance_ron is not None
        ):
            # Dynamically detect inflection month from monthly series
            m_rows = query_all(
                conn,
                """
                SELECT substr(b.cand, 1, 7) AS luna,
                       ROUND(SUM(v.valoare_fara_tva), 2) AS rev,
                       t.target_vanzari AS tgt
                FROM bonuri b
                JOIN vanzari v ON v.id_bon = b.id
                LEFT JOIN target_lunar t ON t.id_magazin = b.id_magazin AND t.luna = substr(b.cand, 1, 7)
                WHERE b.id_magazin = ? AND b.cand >= ? AND b.cand < ?
                GROUP BY 1
                ORDER BY 1
                """,
                (st.id, filters.start_ts, filters.end_ts_excl),
            )
            inflection_note = ""
            if len(m_rows) >= 6:
                for idx in range(2, len(m_rows) - 2):
                    pre = [
                        100.0 * r["rev"] / r["tgt"]
                        for r in m_rows[:idx]
                        if r["tgt"] and r["tgt"] > 0
                    ]
                    post = [
                        100.0 * r["rev"] / r["tgt"]
                        for r in m_rows[idx:]
                        if r["tgt"] and r["tgt"] > 0
                    ]
                    if pre and post and (sum(pre) / len(pre)) >= 90.0 and (sum(post) / len(post)) < 75.0:
                        inflection_note = (
                            f" Performance dropped abruptly from {sum(pre)/len(pre):.1f}% avg attainment "
                            f"to {sum(post)/len(post):.1f}% starting {m_rows[idx]['luna']}."
                        )
                        break

            share_shortfall = (
                abs(st.variance_ron) / abs(total_chain_shortfall) * 100.0
                if total_chain_shortfall < 0
                else 0.0
            )
            alerts.append(
                AlertItem(
                    id=f"store-underperf-{st.id}",
                    severity="critical",
                    category="store_performance",
                    title=f"Sustained Traffic & Target Collapse at {st.nume}",
                    metric_highlight=f"{st.attainment_pct:.1f}% attainment ({st.variance_ron:,.0f} RON)",
                    ron_impact=round(abs(st.variance_ron), 2),
                    affected_entities=[st.nume, st.regiune],
                    evidence=(
                        f"{st.nume} generated {st.revenue_ron:,.0f} RON vs {st.target_ron:,.0f} RON target "
                        f"({st.attainment_pct:.1f}% attainment), accounting for {share_shortfall:.1f}% of the scoped "
                        f"shortfall.{inflection_note}"
                    ),
                    recommended_action=(
                        "Conduct immediate on-site store audit (local competitor entry, staffing, signage) "
                        "and re-baseline monthly targets until footfall recovers."
                    ),
                    drilldown_path="/stores",
                    drilldown_filters={"store_id": st.id},
                )
            )

    # 2. Single-Store Multi-Day Outages (High)
    where_sql, params, _, needs_prod, needs_cat = build_sales_where(filters)
    joins_sql = sales_joins_sql(False, needs_prod, needs_cat)
    outage_months = query_all(
        conn,
        f"""
        WITH sm AS (
            SELECT b.id_magazin, m.nume, m.id_regiune, substr(b.cand, 1, 7) AS luna,
                   ROUND(SUM(v.valoare_fara_tva), 2) AS rev
            FROM bonuri b
            JOIN vanzari v ON v.id_bon = b.id
            JOIN magazine m ON m.id = b.id_magazin
            {joins_sql}
            WHERE {where_sql}
            GROUP BY b.id_magazin, substr(b.cand, 1, 7)
        ),
        sm_lag AS (
            SELECT sm.*, t.target_vanzari AS tgt,
                   LAG(sm.rev) OVER (PARTITION BY sm.id_magazin ORDER BY sm.luna) AS prev_rev
            FROM sm
            LEFT JOIN target_lunar t ON t.id_magazin = sm.id_magazin AND t.luna = sm.luna
        )
        SELECT id_magazin, nume, luna, rev, prev_rev, tgt
        FROM sm_lag
        WHERE prev_rev > 0 AND (rev - prev_rev) / prev_rev < -0.50
          AND (tgt IS NULL OR (100.0 * rev / tgt) < 50.0)
        """,
        params,
    )
    for om in outage_months:
        sid = int(om["id_magazin"])
        luna = om["luna"]
        d_rows = query_all(
            conn,
            "SELECT DISTINCT substr(cand, 1, 10) AS d FROM bonuri WHERE id_magazin = ? AND substr(cand, 1, 7) = ? ORDER BY 1",
            (sid, luna),
        )
        max_gap = 0
        gap_span = ""
        days = [date.fromisoformat(r["d"]) for r in d_rows]
        for idx in range(1, len(days)):
            g = (days[idx] - days[idx - 1]).days - 1
            if g > max_gap:
                max_gap = g
                gap_span = f"{days[idx - 1]} to {days[idx]}"
        est_loss = round(max(0.0, float(om["prev_rev"]) - float(om["rev"])), 2)
        mom_pct = 100.0 * (float(om["rev"]) - float(om["prev_rev"])) / float(om["prev_rev"])
        alerts.append(
            AlertItem(
                id=f"store-outage-{sid}-{luna}",
                severity="high",
                category="store_performance",
                title=f"Operating Outage at {om['nume']} ({luna})",
                metric_highlight=f"{mom_pct:.1f}% MoM | {max_gap} zero-sale days",
                ron_impact=est_loss,
                affected_entities=[om["nume"]],
                evidence=(
                    f"{om['nume']} dropped from {om['prev_rev']:,.0f} RON to {om['rev']:,.0f} RON in {luna} "
                    f"({mom_pct:.1f}% MoM), with {len(days)} active days and a {max_gap}-day gap ({gap_span})."
                ),
                recommended_action=(
                    "Log root cause (renovation, POS/IT outage, or emergency closure) in historical reporting "
                    "and adjust YoY/monthly benchmarks for that period."
                ),
                drilldown_path="/stores",
                drilldown_filters={"store_id": sid},
            )
        )

    # 3 & 4. Net-Loss and Margin-Eroding Promotions
    for c in promos_data.campaigns:
        if c.verdict == "net_loss":
            alerts.append(
                AlertItem(
                    id=f"promo-loss-{c.id}",
                    severity="critical",
                    category="promotions",
                    title=f"Net-Loss Promotion: {c.nume}",
                    metric_highlight=f"{c.profit_ron:,.0f} RON profit ({c.margin_pct:.1f}% margin)",
                    ron_impact=round(abs(c.below_cost_loss_ron) + abs(c.profit_ron), 2),
                    affected_entities=[c.nume],
                    evidence=(
                        f"'{c.nume}' ({c.tip}) generated {c.revenue_ron:,.0f} RON revenue after {c.discount_ron:,.0f} RON "
                        f"in discounts, resulting in {c.profit_ron:,.0f} RON net profit ({c.margin_pct:.1f}% margin) "
                        f"and {c.below_cost_lines:,} positive-qty below-cost lines ({c.below_cost_loss_ron:,.0f} RON loss)."
                    ),
                    recommended_action=(
                        "Retire unconditional 2+1 mechanics on sub-33% margin SKUs; replace with "
                        "minimum-basket thresholds or margin-capped bundle discounts (max 15%)."
                    ),
                    drilldown_path="/promotions",
                    drilldown_filters={},
                )
            )
        elif c.verdict == "margin_eroding" and (c.below_cost_lines >= 50 or c.profit_uplift_pct < -25.0):
            impact = round(
                abs(c.below_cost_loss_ron)
                if c.below_cost_loss_ron < 0
                else max(0.0, (c.profit_per_day_pre28 - c.profit_per_day_during) * c.days),
                2,
            )
            alerts.append(
                AlertItem(
                    id=f"promo-erode-{c.id}",
                    severity="high",
                    category="promotions",
                    title=f"Margin-Eroding Promotion: {c.nume}",
                    metric_highlight=f"{c.margin_pct:.1f}% margin | {c.profit_uplift_pct:+.1f}% daily profit",
                    ron_impact=impact,
                    affected_entities=[c.nume],
                    evidence=(
                        f"'{c.nume}' yielded {c.margin_pct:.1f}% margin ({c.below_cost_lines:,} below-cost lines "
                        f"costing {c.below_cost_loss_ron:,.0f} RON) and shifted daily SKU profit from "
                        f"{c.profit_per_day_pre28:,.0f} to {c.profit_per_day_during:,.0f} RON/day ({c.profit_uplift_pct:+.1f}%)."
                    ),
                    recommended_action=(
                        "Cap discount depth by SKU gross-margin floor so promotional unit price never falls below cost_achizitie."
                    ),
                    drilldown_path="/promotions",
                    drilldown_filters={},
                )
            )

    # 5. YoY Over-Discounting Alert
    for yoy in promos_data.yoy_comparisons:
        if yoy.profit_delta_ron < -10000 and yoy.disc_delta_ron > 10000:
            alerts.append(
                AlertItem(
                    id=f"promo-yoy-{yoy.campaign_2025.id}-{yoy.campaign_2026.id}",
                    severity="high",
                    category="promotions",
                    title=f"YoY Over-Discounting: {yoy.label}",
                    metric_highlight=f"{yoy.profit_delta_ron:,.0f} RON profit | {yoy.margin_delta_pp:+.1f} pp margin",
                    ron_impact=round(abs(yoy.profit_delta_ron), 2),
                    affected_entities=[yoy.campaign_2025.nume, yoy.campaign_2026.nume],
                    evidence=(
                        f"Increasing discount from {yoy.campaign_2025.valoare:.0f}% to {yoy.campaign_2026.valoare:.0f}% "
                        f"on identical SKUs changed revenue by {yoy.rev_delta_ron:+,.0f} RON while increasing discounts "
                        f"by {yoy.disc_delta_ron:+,.0f} RON and cutting profit by {yoy.profit_delta_ron:,.0f} RON."
                    ),
                    recommended_action=(
                        "Revert next seasonal campaign to the 15% tier; extra 5% discount fails to generate incremental volume."
                    ),
                    drilldown_path="/promotions",
                    drilldown_filters={},
                )
            )

    # 6. High-Velocity Stockouts & Weekly Delivery Clustering (High)
    if inv_data.kpis.active_zero_stock_pairs > 0:
        high_risk_stores = [s for s in inv_data.store_cadence if s.zero_active_skus >= 15]
        top_skus = inv_data.top_stocked_out_skus[:3]
        store_names = [
            f"{s.store_name.replace('Farmacia Lumen ', '')} ({s.zero_active_skus} SKUs, last deliv {s.last_delivery_date})"
            for s in high_risk_stores[:4]
        ]
        sku_names = [f"{k.product_name} ({k.zero_stores} stores)" for k in top_skus]
        alerts.append(
            AlertItem(
                id="inventory-stockouts",
                severity="high",
                category="inventory",
                title="Active High-Velocity Stockouts Clustered in Early-Week Delivery Stores",
                metric_highlight=(
                    f"{inv_data.kpis.active_zero_stock_pairs} zero-stock pairs | "
                    f"{inv_data.kpis.rev_90d_at_risk_ron:,.0f} RON 90d risk"
                ),
                ron_impact=inv_data.kpis.rev_90d_at_risk_ron,
                affected_entities=[s.store_name for s in high_risk_stores[:4]] + [k.product_name for k in top_skus],
                evidence=(
                    f"{inv_data.kpis.active_zero_stock_pairs} active store-SKU pairs are at 0 stock and "
                    f"{inv_data.kpis.low_stock_share_pct:.1f}% ({inv_data.kpis.low_stock_pairs:,}) hold 1–5 units. "
                    f"Affected stores: {'; '.join(store_names) if store_names else 'multiple pharmacies'}. "
                    f"Top stocked-out SKUs: {', '.join(sku_names)}."
                ),
                recommended_action=(
                    "Execute immediate intra-region stock transfers for high-ticket monitors/dermo SKUs and add "
                    "a mid-week replenishment drop for high-velocity pharmacies."
                ),
                drilldown_path="/inventory",
                drilldown_filters={},
            )
        )

    # 7. Systemic Target Calibration Bias (Medium)
    loy_where, loy_params, l_mag, l_prod, l_cat = build_sales_where(filters)
    loy_joins = sales_joins_sql(l_mag, l_prod, l_cat)
    if stores_data.target_available:
        m_rev_rows = query_all(
            conn,
            f"""
            SELECT substr(b.cand, 1, 7) AS luna, ROUND(SUM(v.valoare_fara_tva), 2) AS rev
            FROM bonuri b
            JOIN vanzari v ON v.id_bon = b.id
            {loy_joins}
            WHERE {loy_where}
            GROUP BY 1
            """,
            loy_params,
        )
        tgt_by_month = compute_targets(conn, filters)["by_month"]
        months_with_tgt = [
            100.0 * float(r["rev"]) / tgt_by_month[r["luna"]]
            for r in m_rev_rows
            if tgt_by_month.get(r["luna"], 0) > 0
        ]
        missed_months = [att for att in months_with_tgt if att < 100.0]
        max_store_att = max(
            (s.attainment_pct for s in stores_data.stores if s.attainment_pct is not None),
            default=100.0,
        )
        if len(months_with_tgt) >= 6 and len(missed_months) / len(months_with_tgt) >= 0.85 and max_store_att < 99.0:
            non_outlier_var = sum(
                min(0.0, s.variance_ron)
                for s in stores_data.stores
                if s.variance_ron is not None and (s.attainment_pct is None or s.attainment_pct >= 80.0)
            )
            alerts.append(
                AlertItem(
                    id="target-calibration-bias",
                    severity="medium",
                    category="store_performance",
                    title="Systemic Target Calibration Bias Across All Pharmacies",
                    metric_highlight=f"{len(missed_months)}/{len(months_with_tgt)} months below target (max store {max_store_att:.1f}%)",
                    ron_impact=round(abs(non_outlier_var), 2),
                    affected_entities=["All Regions", "target_lunar"],
                    evidence=(
                        f"{len(missed_months)} of {len(months_with_tgt)} months missed chain target, and even the "
                        f"top-performing store peaked at {max_store_att:.1f}% attainment "
                        f"(chain avg ex-outliers: {stores_data.chain_avg_excl_outliers_pct:.2f}%)."
                    ),
                    recommended_action=(
                        "Recalibrate FY target-setting model by ~4–5% to reflect realistic store capacity and "
                        "prevent bonus-demotivation across healthy stores."
                    ),
                    drilldown_path="/stores",
                    drilldown_filters={},
                )
            )

    # 8. Loyalty Program Flat AOV & Dormancy (Medium)
    loy_row = query_one(
        conn,
        f"""
        SELECT COUNT(DISTINCT CASE WHEN b.id_client IS NOT NULL THEN b.id END) AS card_rec,
               COUNT(DISTINCT CASE WHEN b.id_client IS NULL THEN b.id END) AS nocard_rec,
               COALESCE(SUM(CASE WHEN b.id_client IS NOT NULL THEN v.valoare_fara_tva ELSE 0 END), 0) AS card_rev,
               COALESCE(SUM(CASE WHEN b.id_client IS NULL THEN v.valoare_fara_tva ELSE 0 END), 0) AS nocard_rev,
               COALESCE(SUM(CASE WHEN b.id_client IS NOT NULL THEN v.profit ELSE 0 END), 0) AS card_prof,
               COALESCE(SUM(CASE WHEN b.id_client IS NULL THEN v.profit ELSE 0 END), 0) AS nocard_prof
        FROM bonuri b
        JOIN vanzari v ON v.id_bon = b.id
        {loy_joins}
        WHERE {loy_where}
        """,
        loy_params,
    )
    c_rec = int(loy_row["card_rec"])
    n_rec = int(loy_row["nocard_rec"])
    c_rev = float(loy_row["card_rev"])
    n_rev = float(loy_row["nocard_rev"])
    card_aov = c_rev / c_rec if c_rec else 0.0
    nocard_aov = n_rev / n_rec if n_rec else 0.0
    card_mgn = 100.0 * float(loy_row["card_prof"]) / c_rev if c_rev else 0.0
    nocard_mgn = 100.0 * float(loy_row["nocard_prof"]) / n_rev if n_rev else 0.0
    card_share = 100.0 * c_rec / (c_rec + n_rec) if (c_rec + n_rec) else 0.0

    client_reg_where = "WHERE c_reg.id_regiune = :region_id" if filters.region_id is not None else ""
    dorm_row = query_one(
        conn,
        f"""
        WITH v_cnt AS (
            SELECT b.id_client, COUNT(DISTINCT b.id) AS visits
            FROM bonuri b
            JOIN vanzari v ON v.id_bon = b.id
            {loy_joins}
            WHERE b.id_client IS NOT NULL AND ({loy_where})
            GROUP BY b.id_client
        )
        SELECT COUNT(*) AS total_members,
               SUM(CASE WHEN COALESCE(v_cnt.visits, 0) = 0 THEN 1 ELSE 0 END) AS dormant,
               SUM(CASE WHEN v_cnt.visits = 1 THEN 1 ELSE 0 END) AS one_time
        FROM clienti c_reg
        LEFT JOIN v_cnt ON v_cnt.id_client = c_reg.id
        {client_reg_where}
        """,
        loy_params,
    )
    total_members = int(dorm_row["total_members"]) if dorm_row else 0
    dormant_members = int(dorm_row["dormant"] or 0) if dorm_row else 0
    one_time_members = int(dorm_row["one_time"] or 0) if dorm_row else 0
    aov_diff = abs(card_aov - nocard_aov)
    dormant_pct = 100.0 * dormant_members / total_members if total_members else 0.0

    if aov_diff < 3.0 or dormant_pct >= 4.0:
        alerts.append(
            AlertItem(
                id="loyalty-flat-uplift",
                severity="medium",
                category="loyalty",
                title="Loyalty Program Shows Zero Basket-Size Uplift & Dormant Cohort",
                metric_highlight=(
                    f"{card_aov:.2f} vs {nocard_aov:.2f} RON AOV | "
                    f"{dormant_members:,} dormant"
                ),
                ron_impact=round(dormant_members * card_aov, 2),
                affected_entities=[f"{dormant_members:,} Dormant Members", f"{one_time_members:,} One-Time Buyers"],
                evidence=(
                    f"Loyalty cards cover {card_share:.1f}% of receipts, yet card AOV "
                    f"({card_aov:.2f} RON) and margin ({card_mgn:.2f}%) "
                    f"are virtually identical to non-card shoppers ({nocard_aov:.2f} RON, "
                    f"{nocard_mgn:.2f}%). {dormant_members:,} enrolled members "
                    f"({dormant_pct:.1f}%) recorded 0 visits."
                ),
                recommended_action=(
                    "Introduce tiered basket-threshold perks (e.g. bonus points above 130 RON) and launch a "
                    "win-back SMS/email campaign targeting dormant and one-time cardholders."
                ),
                drilldown_path="/customers",
                drilldown_filters={},
            )
        )

    # 9. Stray Test Promo in Catalog (Low)
    for tp in promos_data.excluded_test_promos:
        alerts.append(
            AlertItem(
                id=f"hygiene-test-promo-{tp.id}",
                severity="low",
                category="data_hygiene",
                title=f"Stray Test Promotion Record in Production Catalog (#{tp.id})",
                metric_highlight=f"'{tp.nume}' ({tp.valoare:.0f}% {tp.tip}, 0 SKUs)",
                ron_impact=0.0,
                affected_entities=[f"oferte.id={tp.id}"],
                evidence=(
                    f"Promotion #{tp.id} ('{tp.nume}', window {tp.inceput}..{tp.sfarsit}) exists in `oferte` "
                    "with 0 linked products and 0 sales; excluded automatically from campaign KPIs."
                ),
                recommended_action="Archive or delete test promotion row from production `oferte` table.",
                drilldown_path="/promotions",
                drilldown_filters={},
            )
        )

    if severity is not None:
        alerts = [a for a in alerts if a.severity == severity]
    if category is not None:
        alerts = [a for a in alerts if a.category == category]

    alerts.sort(key=lambda a: (SEVERITY_RANK[a.severity], -abs(a.ron_impact)))

    counts = AlertCounts(
        critical=sum(1 for a in alerts if a.severity == "critical"),
        high=sum(1 for a in alerts if a.severity == "high"),
        medium=sum(1 for a in alerts if a.severity == "medium"),
        low=sum(1 for a in alerts if a.severity == "low"),
    )
    total_impact = round(sum(a.ron_impact for a in alerts), 2)

    return AlertsResponse(
        currency=settings.currency_label,
        counts=counts,
        total_quantified_impact_ron=total_impact,
        alerts=alerts,
    )
