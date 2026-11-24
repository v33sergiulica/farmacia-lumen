"""Dynamic, SQL-grounded Operational Problems & Recommended Actions Feed."""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query

from ..config import settings
from ..db import get_db, query_all
from ..schemas import AlertCounts, AlertItem, AlertsResponse
from ..services.cache import cached_call, make_cache_key
from ..services.filters import (
    GlobalFilters,
    compute_targets,
    get_global_filters,
)
from .customers import get_customers
from .inventory import get_inventory
from .promotions import get_promotions
from .stores import fetch_store_month_agg, get_stores

router = APIRouter(tags=["alerts"])

SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _compute_all_alerts(filters: GlobalFilters, conn: sqlite3.Connection) -> list[AlertItem]:
    alerts: list[AlertItem] = []

    sm_rows = fetch_store_month_agg(conn, filters)
    stores_data = get_stores(sort_by="attainment_pct", filters=filters, conn=conn)
    promos_data = get_promotions(filters=filters, conn=conn)
    inv_data = get_inventory(low_stock_max=5, limit=25, filters=filters, conn=conn)
    cust_data = get_customers(filters=filters, conn=conn)

    # Index store-month rows in memory (<= 364 rows)
    by_store_months: dict[int, list[dict[str, object]]] = {}
    monthly_rev_totals: dict[str, float] = {}
    for r in sm_rows:
        sid = int(r["id_magazin"])
        luna = str(r["luna"])
        rev = float(r["rev"])
        by_store_months.setdefault(sid, []).append(r)
        monthly_rev_totals[luna] = monthly_rev_totals.get(luna, 0.0) + rev

    # Per-store monthly targets when target_available
    store_month_targets: dict[tuple[int, str], float] = {}
    if stores_data.target_available:
        t_rows = query_all(
            conn,
            "SELECT id_magazin, luna, target_vanzari FROM target_lunar",
        )
        store_month_targets = {
            (int(r["id_magazin"]), str(r["luna"])): float(r["target_vanzari"])
            for r in t_rows
        }

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
            m_rows = by_store_months.get(st.id, [])
            inflection_note = ""
            if len(m_rows) >= 6:
                atts = [
                    (
                        str(r["luna"]),
                        100.0 * float(r["rev"]) / store_month_targets[(st.id, str(r["luna"]))],
                    )
                    for r in m_rows
                    if store_month_targets.get((st.id, str(r["luna"])), 0.0) > 0
                ]
                best_break: tuple[float, str, float, float] | None = None
                for idx in range(2, len(atts) - 2):
                    pre_vals = [a for _, a in atts[:idx]]
                    post_vals = [a for _, a in atts[idx:]]
                    avg_pre = sum(pre_vals) / len(pre_vals)
                    avg_post = sum(post_vals) / len(post_vals)
                    # Require true step-down at idx (previous month healthy, current month dropped)
                    if (
                        avg_pre >= 90.0
                        and avg_post < 75.0
                        and atts[idx - 1][1] >= 85.0
                        and atts[idx][1] < 80.0
                    ):
                        gap = avg_pre - avg_post
                        if best_break is None or gap > best_break[0]:
                            best_break = (gap, atts[idx][0], avg_pre, avg_post)
                if best_break is not None:
                    _, break_month, avg_pre, avg_post = best_break
                    inflection_note = (
                        f" Performance dropped abruptly from {avg_pre:.1f}% avg attainment "
                        f"to {avg_post:.1f}% starting {break_month}."
                    )

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
    store_name_map = {s.id: s.nume for s in stores_data.stores}
    for sid, m_rows in by_store_months.items():
        for idx in range(1, len(m_rows)):
            prev_rev = float(m_rows[idx - 1]["rev"])
            rev = float(m_rows[idx]["rev"])
            luna = str(m_rows[idx]["luna"])
            tgt = store_month_targets.get((sid, luna))
            if prev_rev > 0 and (rev - prev_rev) / prev_rev < -0.50 and (
                tgt is None or (100.0 * rev / tgt) < 50.0
            ):
                d_rows = query_all(
                    conn,
                    "SELECT DISTINCT substr(cand, 1, 10) AS d FROM bonuri WHERE id_magazin = ? AND cand >= ? AND cand < ? ORDER BY 1",
                    (sid, f"{luna}-01 00:00:00", f"{luna}-32"),
                )
                max_gap = 0
                gap_span = ""
                days = [date.fromisoformat(r["d"]) for r in d_rows]
                for d_idx in range(1, len(days)):
                    g = (days[d_idx] - days[d_idx - 1]).days - 1
                    if g > max_gap:
                        max_gap = g
                        gap_span = f"{days[d_idx - 1]} to {days[d_idx]}"
                est_loss = round(max(0.0, prev_rev - rev), 2)
                mom_pct = 100.0 * (rev - prev_rev) / prev_rev
                s_name = store_name_map.get(sid, f"Store {sid}")
                alerts.append(
                    AlertItem(
                        id=f"store-outage-{sid}-{luna}",
                        severity="high",
                        category="store_performance",
                        title=f"Operating Outage at {s_name} ({luna})",
                        metric_highlight=f"{mom_pct:.1f}% MoM | {max_gap} zero-sale days",
                        ron_impact=est_loss,
                        affected_entities=[s_name],
                        evidence=(
                            f"{s_name} dropped from {prev_rev:,.0f} RON to {rev:,.0f} RON in {luna} "
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
            # Use non-overlapping below-cost line loss (fallback to abs net profit loss if 0)
            below_cost_impact = (
                round(abs(c.below_cost_loss_ron), 2)
                if c.below_cost_loss_ron < 0
                else round(abs(c.profit_ron), 2)
            )
            alerts.append(
                AlertItem(
                    id=f"promo-loss-{c.id}",
                    severity="critical",
                    category="promotions",
                    title=f"Net-Loss Promotion: {c.nume}",
                    metric_highlight=(
                        f"{c.profit_ron:,.0f} RON net profit ({c.margin_pct:.1f}% margin) | "
                        f"{abs(c.below_cost_loss_ron):,.0f} RON below-cost loss"
                    ),
                    ron_impact=below_cost_impact,
                    affected_entities=[c.nume],
                    evidence=(
                        f"'{c.nume}' ({c.tip}) generated {c.revenue_ron:,.0f} RON revenue after {c.discount_ron:,.0f} RON "
                        f"in discounts, resulting in {c.profit_ron:,.0f} RON net profit ({c.margin_pct:.1f}% margin). "
                        f"Impact reflects the {abs(c.below_cost_loss_ron):,.0f} RON gross loss across "
                        f"{c.below_cost_lines:,} positive-qty below-cost lines."
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
    if stores_data.target_available:
        tgt_by_month = compute_targets(conn, filters)["by_month"]
        months_with_tgt = [
            100.0 * monthly_rev_totals.get(luna, 0.0) / tgt_val
            for luna, tgt_val in sorted(tgt_by_month.items())
            if tgt_val > 0
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
    aov_diff = abs(cust_data.penetration.card_aov_ron - cust_data.penetration.nocard_aov_ron)
    dormant_pct = (
        100.0 * cust_data.dormant_members / cust_data.total_registered_members
        if cust_data.total_registered_members
        else 0.0
    )
    if aov_diff < 3.0 or dormant_pct >= 4.0:
        alerts.append(
            AlertItem(
                id="loyalty-flat-uplift",
                severity="medium",
                category="loyalty",
                title="Loyalty Program Shows Zero Basket-Size Uplift & Dormant Cohort",
                metric_highlight=(
                    f"{cust_data.penetration.card_aov_ron:.2f} vs {cust_data.penetration.nocard_aov_ron:.2f} RON AOV | "
                    f"{cust_data.dormant_members:,} dormant"
                ),
                ron_impact=round(cust_data.dormant_members * cust_data.penetration.card_aov_ron, 2),
                affected_entities=[f"{cust_data.dormant_members:,} Dormant Members", f"{cust_data.one_time_members:,} One-Time Buyers"],
                evidence=(
                    f"Loyalty cards cover {cust_data.penetration.card_receipt_share_pct:.1f}% of receipts, yet card AOV "
                    f"({cust_data.penetration.card_aov_ron:.2f} RON) and margin ({cust_data.penetration.card_margin_pct:.2f}%) "
                    f"are virtually identical to non-card shoppers ({cust_data.penetration.nocard_aov_ron:.2f} RON, "
                    f"{cust_data.penetration.nocard_margin_pct:.2f}%). {cust_data.dormant_members:,} enrolled members "
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

    alerts.sort(key=lambda a: (SEVERITY_RANK[a.severity], -abs(a.ron_impact)))
    return alerts


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
    all_alerts = cached_call(
        make_cache_key("alerts_all", filters),
        lambda: _compute_all_alerts(filters, conn),
    )

    filtered = all_alerts
    if severity is not None:
        filtered = [a for a in filtered if a.severity == severity]
    if category is not None:
        filtered = [a for a in filtered if a.category == category]

    counts = AlertCounts(
        critical=sum(1 for a in filtered if a.severity == "critical"),
        high=sum(1 for a in filtered if a.severity == "high"),
        medium=sum(1 for a in filtered if a.severity == "medium"),
        low=sum(1 for a in filtered if a.severity == "low"),
    )
    total_impact = round(sum(a.ron_impact for a in filtered), 2)

    return AlertsResponse(
        currency=settings.currency_label,
        counts=counts,
        total_quantified_impact_ron=total_impact,
        alerts=filtered,
    )
