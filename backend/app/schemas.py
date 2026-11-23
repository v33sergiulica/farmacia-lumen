"""Pydantic response schemas for Farmacia Lumen BI API."""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    db_mode: str
    currency: str
    date_min: str
    date_max: str
    tables_verified: int


class RegionOption(BaseModel):
    id: int
    nume: str


class StoreOption(BaseModel):
    id: int
    nume: str
    oras: str
    id_regiune: int
    deschis_la: str
    inchis_la: str | None
    status: Literal["active", "opened_mid_period", "closed"]


class SubcategoryOption(BaseModel):
    id: int
    nume: str


class CategoryOption(BaseModel):
    id: int
    nume: str
    subcategories: list[SubcategoryOption]


class FiltersResponse(BaseModel):
    date_min: str
    date_max: str
    currency: str
    regions: list[RegionOption]
    stores: list[StoreOption]
    categories: list[CategoryOption]


class OverviewKpis(BaseModel):
    net_revenue_ron: float
    gross_revenue_ron: float
    gross_profit_ron: float
    margin_pct: float
    discount_ron: float
    units_net: int
    receipts: int
    aov_ron: float
    target_ron: float | None
    attainment_pct: float | None
    variance_ron: float | None
    target_available: bool
    return_lines: int
    return_value_ron: float
    return_rate_units_pct: float
    rev_vs_prev_period_pct: float | None


class OverviewSeriesPoint(BaseModel):
    period: str
    revenue_ron: float
    target_ron: float | None
    attainment_pct: float | None
    profit_ron: float
    margin_pct: float
    receipts: int
    aov_ron: float


class OverviewAnnotation(BaseModel):
    period: str
    label: str
    detail: str
    type: str


class CategoryMixItem(BaseModel):
    id: int
    nume: str
    revenue_ron: float
    share_pct: float
    profit_ron: float
    margin_pct: float
    units: int


class ProductSummaryItem(BaseModel):
    id: int
    nume: str
    brand: str
    category: str
    activ: int
    revenue_ron: float
    profit_ron: float
    margin_pct: float
    units: int
    return_rate_pct: float


class PriceWaveSummary(BaseModel):
    month: str
    repriced_skus: int
    total_skus: int
    avg_price_chg_pct: float
    avg_cost_chg_pct: float


class OverviewResponse(BaseModel):
    currency: str
    granularity: str
    kpis: OverviewKpis
    series: list[OverviewSeriesPoint]
    annotations: list[OverviewAnnotation]
    category_mix: list[CategoryMixItem]
    top_products: list[ProductSummaryItem]
    bottom_products: list[ProductSummaryItem]
    price_wave: PriceWaveSummary | None


class RegionPerformance(BaseModel):
    id: int
    nume: str
    store_count: int
    open_stores: int
    revenue_ron: float
    target_ron: float | None
    attainment_pct: float | None
    variance_ron: float | None
    margin_pct: float


class StorePerformance(BaseModel):
    id: int
    nume: str
    regiune: str
    oras: str
    sqm: int
    employees: int
    deschis_la: str
    inchis_la: str | None
    status: Literal["active", "opened_mid_period", "closed"]
    active_months: int
    revenue_ron: float
    target_ron: float | None
    attainment_pct: float | None
    variance_ron: float | None
    rev_per_active_month: float
    rev_per_sqm_month: float
    rev_per_emp_month: float
    profit_ron: float
    margin_pct: float
    receipts: int
    aov_ron: float
    return_rate_pct: float
    anomaly_flags: list[str]


class StoresResponse(BaseModel):
    currency: str
    target_available: bool
    regions: list[RegionPerformance]
    stores: list[StorePerformance]
    chain_avg_attainment_pct: float | None
    chain_avg_excl_outliers_pct: float | None


class StoreTrendPoint(BaseModel):
    period: str
    revenue_ron: float
    target_ron: float | None
    attainment_pct: float | None
    receipts: int
    delivery_qty: int


class SiblingComparison(BaseModel):
    store_id: int
    store_name: str
    series: list[StoreTrendPoint]


class StoreEvent(BaseModel):
    date: str
    title: str
    impact_summary: str


class StoreTransferSummary(BaseModel):
    store_id: int
    store_name: str
    skus: int
    units: int


class StoreTrendResponse(BaseModel):
    currency: str
    granularity: str
    store: StorePerformance
    series: list[StoreTrendPoint]
    sibling_comparison: SiblingComparison | None
    events: list[StoreEvent]
    transfers: list[StoreTransferSummary]


class PromotionsSummary(BaseModel):
    active_campaigns: int
    promo_revenue_ron: float
    promo_rev_share_pct: float
    total_discount_ron: float
    promo_profit_ron: float
    promo_margin_pct: float
    below_cost_lines: int
    below_cost_loss_ron: float


class CampaignPerformance(BaseModel):
    id: int
    nume: str
    tip: str
    valoare: float
    inceput: str
    sfarsit: str
    days: int
    sku_count: int
    revenue_ron: float
    discount_ron: float
    profit_ron: float
    margin_pct: float
    units_net: int
    below_cost_lines: int
    below_cost_loss_ron: float
    rev_per_day_during: float
    rev_per_day_pre28: float
    rev_uplift_pct: float
    profit_per_day_during: float
    profit_per_day_pre28: float
    profit_uplift_pct: float
    verdict: Literal["profitable", "margin_eroding", "net_loss"]


class YoYCampaignComparison(BaseModel):
    label: str
    campaign_2025: CampaignPerformance
    campaign_2026: CampaignPerformance
    rev_delta_ron: float
    disc_delta_ron: float
    profit_delta_ron: float
    margin_delta_pp: float


class ExcludedTestPromo(BaseModel):
    id: int
    nume: str
    tip: str
    valoare: float
    inceput: str
    sfarsit: str
    reason: str


class PromotionsResponse(BaseModel):
    currency: str
    summary: PromotionsSummary
    campaigns: list[CampaignPerformance]
    yoy_comparisons: list[YoYCampaignComparison]
    excluded_test_promos: list[ExcludedTestPromo]


class InventoryKpis(BaseModel):
    total_inv_cost_ron: float
    total_units: int
    open_store_sku_pairs: int
    active_zero_stock_pairs: int
    low_stock_pairs: int
    low_stock_share_pct: float
    dead_stock_90d_pairs: int
    dead_stock_90d_cost_ron: float
    rev_90d_at_risk_ron: float
    ledger_discrepancy_units: int


class StoreCadenceItem(BaseModel):
    store_id: int
    store_name: str
    region: str
    zero_active_skus: int
    low_stock_skus: int
    rev_90d_at_risk_ron: float
    last_delivery_date: str | None
    days_since_last_delivery: int | None
    recent_30d_deliveries: int


class TransferSuggestion(BaseModel):
    store_id: int
    store_name: str
    available_stoc: int
    same_region: bool


class StockoutQueueItem(BaseModel):
    store_id: int
    store_name: str
    region: str
    product_id: int
    product_name: str
    brand: str
    category: str
    stoc: int
    qty_90d: int
    rev_90d_at_risk_ron: float
    last_delivery_date: str | None
    suggested_transfer_from: TransferSuggestion | None


class StockedOutSkuSummary(BaseModel):
    product_id: int
    product_name: str
    brand: str
    category: str
    zero_stores: int
    total_stoc: int
    qty_90d: int
    rev_90d_ron: float


class SlowMoverItem(BaseModel):
    product_id: int
    product_name: str
    category: str
    total_stoc: int
    inv_cost_ron: float
    qty_90d: int
    days_of_supply: float | None


class InventoryResponse(BaseModel):
    currency: str
    date_filter_ignored: bool = Field(default=True)
    snapshot_date: str
    velocity_window_start: str
    kpis: InventoryKpis
    store_cadence: list[StoreCadenceItem]
    stockout_queue: list[StockoutQueueItem]
    top_stocked_out_skus: list[StockedOutSkuSummary]
    slow_movers: list[SlowMoverItem]


class CustomerPenetration(BaseModel):
    card_receipts: int
    nocard_receipts: int
    card_receipt_share_pct: float
    card_revenue_ron: float
    nocard_revenue_ron: float
    card_rev_share_pct: float
    card_aov_ron: float
    nocard_aov_ron: float
    card_margin_pct: float
    nocard_margin_pct: float


class FrequencySegmentItem(BaseModel):
    bucket: str
    members: int
    share_pct: float
    revenue_ron: float
    avg_spend_ron: float


class MonthlyLoyaltyPoint(BaseModel):
    period: str
    card_share_pct: float
    card_aov_ron: float
    nocard_aov_ron: float


class DemographicBucket(BaseModel):
    label: str
    members: int
    receipts: int
    revenue_ron: float
    avg_spend_per_member_ron: float


class CustomersDemographics(BaseModel):
    by_sex: list[DemographicBucket]
    by_age_band: list[DemographicBucket]
    by_region: list[DemographicBucket]


class CustomersResponse(BaseModel):
    currency: str
    total_registered_members: int
    dormant_members: int
    one_time_members: int
    penetration: CustomerPenetration
    frequency_segments: list[FrequencySegmentItem]
    monthly_loyalty_trend: list[MonthlyLoyaltyPoint]
    demographics: CustomersDemographics


class AlertItem(BaseModel):
    id: str
    severity: Literal["critical", "high", "medium", "low"]
    category: Literal[
        "store_performance", "promotions", "inventory", "loyalty", "data_hygiene"
    ]
    title: str
    metric_highlight: str
    ron_impact: float
    affected_entities: list[str]
    evidence: str
    recommended_action: str
    drilldown_path: str
    drilldown_filters: dict[str, str | int] = Field(default_factory=dict)


class AlertCounts(BaseModel):
    critical: int
    high: int
    medium: int
    low: int


class AlertsResponse(BaseModel):
    currency: str
    counts: AlertCounts
    total_quantified_impact_ron: float
    alerts: list[AlertItem]


class AnalystQuestionRequest(BaseModel):
    question: str
    filters: dict[str, str | int | None] | None = None
