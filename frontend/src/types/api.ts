export interface GlobalFilterParams {
  start_date: string;
  end_date: string;
  region_id: number | null;
  store_id: number | null;
  category_id: number | null;
  subcategory_id: number | null;
}

export interface HealthResponse {
  status: string;
  db_mode: string;
  currency: string;
  date_min: string;
  date_max: string;
  tables_verified: number;
}

export interface RegionOption {
  id: number;
  nume: string;
}

export type StoreLifecycleStatus = "active" | "opened_mid_period" | "closed";

export interface StoreOption {
  id: number;
  nume: string;
  oras: string;
  id_regiune: number;
  deschis_la: string;
  inchis_la: string | null;
  status: StoreLifecycleStatus;
}

export interface SubcategoryOption {
  id: number;
  nume: string;
}

export interface CategoryOption {
  id: number;
  nume: string;
  subcategories: SubcategoryOption[];
}

export interface FiltersResponse {
  date_min: string;
  date_max: string;
  currency: string;
  regions: RegionOption[];
  stores: StoreOption[];
  categories: CategoryOption[];
}

export interface OverviewKpis {
  net_revenue_ron: number;
  gross_revenue_ron: number;
  gross_profit_ron: number;
  margin_pct: number;
  discount_ron: number;
  units_net: number;
  receipts: number;
  aov_ron: number;
  target_ron: number | null;
  attainment_pct: number | null;
  variance_ron: number | null;
  target_available: boolean;
  return_lines: number;
  return_value_ron: number;
  return_rate_units_pct: number;
  rev_vs_prev_period_pct: number | null;
}

export interface OverviewSeriesPoint {
  period: string;
  revenue_ron: number;
  target_ron: number | null;
  attainment_pct: number | null;
  profit_ron: number;
  margin_pct: number;
  receipts: number;
  aov_ron: number;
}

export interface OverviewAnnotation {
  period: string;
  label: string;
  detail: string;
  type: string;
}

export interface CategoryMixItem {
  id: number;
  nume: string;
  revenue_ron: number;
  share_pct: number;
  profit_ron: number;
  margin_pct: number;
  units: number;
}

export interface ProductSummaryItem {
  id: number;
  nume: string;
  brand: string;
  category: string;
  activ: number;
  revenue_ron: number;
  profit_ron: number;
  margin_pct: number;
  units: number;
  return_rate_pct: number;
}

export interface PriceWaveSummary {
  month: string;
  repriced_skus: number;
  total_skus: number;
  avg_price_chg_pct: number;
  avg_cost_chg_pct: number;
}

export interface OverviewResponse {
  currency: string;
  granularity: string;
  kpis: OverviewKpis;
  series: OverviewSeriesPoint[];
  annotations: OverviewAnnotation[];
  category_mix: CategoryMixItem[];
  top_products: ProductSummaryItem[];
  bottom_products: ProductSummaryItem[];
  price_wave: PriceWaveSummary | null;
}

export interface RegionPerformance {
  id: number;
  nume: string;
  store_count: number;
  open_stores: number;
  revenue_ron: number;
  target_ron: number | null;
  attainment_pct: number | null;
  variance_ron: number | null;
  margin_pct: number;
}

export interface StorePerformance {
  id: number;
  nume: string;
  regiune: string;
  oras: string;
  sqm: number;
  employees: number;
  deschis_la: string;
  inchis_la: string | null;
  status: StoreLifecycleStatus;
  active_months: number;
  revenue_ron: number;
  target_ron: number | null;
  attainment_pct: number | null;
  variance_ron: number | null;
  rev_per_active_month: number;
  rev_per_sqm_month: number;
  rev_per_emp_month: number;
  profit_ron: number;
  margin_pct: number;
  receipts: number;
  aov_ron: number;
  return_rate_pct: number;
  anomaly_flags: string[];
}

export interface StoresResponse {
  currency: string;
  target_available: boolean;
  regions: RegionPerformance[];
  stores: StorePerformance[];
  chain_avg_attainment_pct: number | null;
  chain_avg_excl_outliers_pct: number | null;
}

export interface StoreTrendPoint {
  period: string;
  revenue_ron: number;
  target_ron: number | null;
  attainment_pct: number | null;
  receipts: number;
  delivery_qty: number;
}

export interface SiblingComparison {
  store_id: number;
  store_name: string;
  series: StoreTrendPoint[];
}

export interface StoreEvent {
  date: string;
  title: string;
  impact_summary: string;
}

export interface StoreTransferSummary {
  store_id: number;
  store_name: string;
  skus: number;
  units: number;
}

export interface StoreTrendResponse {
  currency: string;
  granularity: string;
  store: StorePerformance;
  series: StoreTrendPoint[];
  sibling_comparison: SiblingComparison | null;
  events: StoreEvent[];
  transfers: StoreTransferSummary[];
}

export interface PromotionsSummary {
  active_campaigns: number;
  promo_revenue_ron: number;
  promo_rev_share_pct: number;
  total_discount_ron: number;
  promo_profit_ron: number;
  promo_margin_pct: number;
  below_cost_lines: number;
  below_cost_loss_ron: number;
}

export type CampaignVerdict = "profitable" | "margin_eroding" | "net_loss";

export interface CampaignPerformance {
  id: number;
  nume: string;
  tip: string;
  valoare: number;
  inceput: string;
  sfarsit: string;
  days: number;
  sku_count: number;
  revenue_ron: number;
  discount_ron: number;
  profit_ron: number;
  margin_pct: number;
  units_net: intOrNumber;
  below_cost_lines: number;
  below_cost_loss_ron: number;
  rev_per_day_during: number;
  rev_per_day_pre28: number;
  rev_uplift_pct: number;
  profit_per_day_during: number;
  profit_per_day_pre28: number;
  profit_uplift_pct: number;
  verdict: CampaignVerdict;
}

type intOrNumber = number;

export interface YoYCampaignComparison {
  label: string;
  campaign_2025: CampaignPerformance;
  campaign_2026: CampaignPerformance;
  rev_delta_ron: number;
  disc_delta_ron: number;
  profit_delta_ron: number;
  margin_delta_pp: number;
}

export interface ExcludedTestPromo {
  id: number;
  nume: string;
  tip: string;
  valoare: number;
  inceput: string;
  sfarsit: string;
  reason: string;
}

export interface PromotionsResponse {
  currency: string;
  summary: PromotionsSummary;
  campaigns: CampaignPerformance[];
  yoy_comparisons: YoYCampaignComparison[];
  excluded_test_promos: ExcludedTestPromo[];
}

export interface InventoryKpis {
  total_inv_cost_ron: number;
  total_units: number;
  open_store_sku_pairs: number;
  active_zero_stock_pairs: number;
  low_stock_pairs: number;
  low_stock_share_pct: number;
  dead_stock_90d_pairs: number;
  dead_stock_90d_cost_ron: number;
  rev_90d_at_risk_ron: number;
  ledger_discrepancy_units: number;
}

export interface StoreCadenceItem {
  store_id: number;
  store_name: string;
  region: string;
  zero_active_skus: number;
  low_stock_skus: number;
  rev_90d_at_risk_ron: number;
  last_delivery_date: string | null;
  days_since_last_delivery: number | null;
  recent_30d_deliveries: number;
}

export interface TransferSuggestion {
  store_id: number;
  store_name: string;
  available_stoc: number;
  same_region: boolean;
}

export interface StockoutQueueItem {
  store_id: number;
  store_name: string;
  region: string;
  product_id: number;
  product_name: string;
  brand: string;
  category: string;
  stoc: number;
  qty_90d: number;
  rev_90d_at_risk_ron: number;
  last_delivery_date: string | null;
  suggested_transfer_from: TransferSuggestion | null;
}

export interface StockedOutSkuSummary {
  product_id: number;
  product_name: string;
  brand: string;
  category: string;
  zero_stores: number;
  total_stoc: number;
  qty_90d: number;
  rev_90d_ron: floatOrNumber;
}

type floatOrNumber = number;

export interface SlowMoverItem {
  product_id: number;
  product_name: string;
  category: string;
  total_stoc: number;
  inv_cost_ron: number;
  qty_90d: number;
  days_of_supply: number | null;
}

export interface InventoryResponse {
  currency: string;
  date_filter_ignored: boolean;
  snapshot_date: string;
  velocity_window_start: string;
  kpis: InventoryKpis;
  store_cadence: StoreCadenceItem[];
  stockout_queue: StockoutQueueItem[];
  top_stocked_out_skus: StockedOutSkuSummary[];
  slow_movers: SlowMoverItem[];
}

export interface CustomerPenetration {
  card_receipts: number;
  nocard_receipts: number;
  card_receipt_share_pct: number;
  card_revenue_ron: number;
  nocard_revenue_ron: number;
  card_rev_share_pct: number;
  card_aov_ron: number;
  nocard_aov_ron: number;
  card_margin_pct: number;
  nocard_margin_pct: number;
}

export interface FrequencySegmentItem {
  bucket: string;
  members: number;
  share_pct: number;
  revenue_ron: number;
  avg_spend_ron: number;
}

export interface MonthlyLoyaltyPoint {
  period: string;
  card_share_pct: number;
  card_aov_ron: number;
  nocard_aov_ron: number;
}

export interface DemographicBucket {
  label: string;
  members: number;
  receipts: number;
  revenue_ron: number;
  avg_spend_per_member_ron: number;
}

export interface CustomersDemographics {
  by_sex: DemographicBucket[];
  by_age_band: DemographicBucket[];
  by_region: DemographicBucket[];
}

export interface CustomersResponse {
  currency: string;
  total_registered_members: number;
  dormant_members: number;
  one_time_members: number;
  penetration: CustomerPenetration;
  frequency_segments: FrequencySegmentItem[];
  monthly_loyalty_trend: MonthlyLoyaltyPoint[];
  demographics: CustomersDemographics;
}

export type AlertSeverity = "critical" | "high" | "medium" | "low";
export type AlertCategory =
  | "store_performance"
  | "promotions"
  | "inventory"
  | "loyalty"
  | "data_hygiene";

export interface AlertItem {
  id: string;
  severity: AlertSeverity;
  category: AlertCategory;
  title: string;
  metric_highlight: string;
  ron_impact: number;
  affected_entities: string[];
  evidence: string;
  recommended_action: string;
  drilldown_path: string;
  drilldown_filters: Record<string, string | number>;
}

export interface AlertCounts {
  critical: number;
  high: number;
  medium: number;
  low: number;
}

export interface AlertsResponse {
  currency: string;
  counts: AlertCounts;
  total_quantified_impact_ron: number;
  alerts: AlertItem[];
}

export interface AnalystResponse {
  answer: string;
  sql: string;
  columns: string[];
  rows: Array<Record<string, unknown>>;
  row_count: number;
  truncated?: boolean;
  execution_ms: number;
  retries_used: number;
  provider?: string;
}
