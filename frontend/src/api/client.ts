import { useEffect } from "react";
import { keepPreviousData, QueryClient, useQuery } from "@tanstack/react-query";
import type {
  AlertsResponse,
  AlertCategory,
  AlertSeverity,
  AnalystResponse,
  CustomersResponse,
  FiltersResponse,
  GlobalFilterParams,
  InventoryResponse,
  OverviewResponse,
  PromotionsResponse,
  StoresResponse,
  StoreTrendResponse,
} from "../types/api";
import { DB_MAX_DATE, DB_MIN_DATE } from "../utils/format";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: Infinity,
      gcTime: 30 * 60 * 1000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function toQueryString(params: Record<string, string | number | null | undefined>): string {
  const sp = new URLSearchParams();
  for (const [key, val] of Object.entries(params)) {
    if (val !== null && val !== undefined && val !== "") {
      sp.set(key, String(val));
    }
  }
  const qs = sp.toString();
  return qs ? `?${qs}` : "";
}

export async function apiGet<T>(
  path: string,
  params: Record<string, string | number | null | undefined> = {},
): Promise<T> {
  const res = await fetch(`/api/v1${path}${toQueryString(params)}`);
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const json = (await res.json()) as { detail?: string };
      if (json.detail) detail = json.detail;
    } catch {
      // keep status text
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`/api/v1${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const json = (await res.json()) as { detail?: string };
      if (json.detail) detail = json.detail;
    } catch {
      // keep status text
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

function filterParamsRecord(filters: GlobalFilterParams): Record<string, string | number | null> {
  return {
    start_date: filters.start_date,
    end_date: filters.end_date,
    region_id: filters.region_id,
    store_id: filters.store_id,
    category_id: filters.category_id,
    subcategory_id: filters.subcategory_id,
  };
}

export function useFiltersMeta() {
  return useQuery({
    queryKey: ["filters"],
    queryFn: () => apiGet<FiltersResponse>("/filters"),
  });
}

export function useOverview(filters: GlobalFilterParams, granularity: "month" | "week") {
  return useQuery({
    queryKey: ["overview", filters, granularity],
    queryFn: () =>
      apiGet<OverviewResponse>("/overview", {
        ...filterParamsRecord(filters),
        granularity,
      }),
    placeholderData: keepPreviousData,
  });
}

export function useStores(
  filters: GlobalFilterParams,
  sortBy:
    | "attainment_pct"
    | "revenue_ron"
    | "rev_per_active_month"
    | "rev_per_sqm_month"
    | "margin_pct",
) {
  return useQuery({
    queryKey: ["stores", filters, sortBy],
    queryFn: () =>
      apiGet<StoresResponse>("/stores", {
        ...filterParamsRecord(filters),
        sort_by: sortBy,
      }),
    placeholderData: keepPreviousData,
  });
}

export function useStoreTrend(
  storeId: number | null,
  filters: GlobalFilterParams,
  granularity: "month" | "week",
) {
  return useQuery({
    queryKey: [
      "store_trend",
      storeId,
      filters.start_date,
      filters.end_date,
      filters.category_id,
      filters.subcategory_id,
      granularity,
    ],
    queryFn: () =>
      apiGet<StoreTrendResponse>(`/stores/${storeId}/trend`, {
        start_date: filters.start_date,
        end_date: filters.end_date,
        category_id: filters.category_id,
        subcategory_id: filters.subcategory_id,
        granularity,
      }),
    enabled: storeId !== null,
    placeholderData: keepPreviousData,
  });
}

export function usePromotions(filters: GlobalFilterParams) {
  return useQuery({
    queryKey: ["promotions", filters],
    queryFn: () => apiGet<PromotionsResponse>("/promotions", filterParamsRecord(filters)),
    placeholderData: keepPreviousData,
  });
}

export function useInventory(filters: GlobalFilterParams, limit = 50) {
  // Inventory ignores start_date/end_date on the backend, so exclude dates from queryKey for instant cache hits.
  return useQuery({
    queryKey: [
      "inventory",
      filters.region_id,
      filters.store_id,
      filters.category_id,
      filters.subcategory_id,
      limit,
    ],
    queryFn: () =>
      apiGet<InventoryResponse>("/inventory", {
        region_id: filters.region_id,
        store_id: filters.store_id,
        category_id: filters.category_id,
        subcategory_id: filters.subcategory_id,
        limit,
      }),
    placeholderData: keepPreviousData,
  });
}

export function useCustomers(filters: GlobalFilterParams) {
  return useQuery({
    queryKey: ["customers", filters],
    queryFn: () => apiGet<CustomersResponse>("/customers", filterParamsRecord(filters)),
    placeholderData: keepPreviousData,
  });
}

export function useAlerts(
  filters: GlobalFilterParams,
  severity: AlertSeverity | null = null,
  category: AlertCategory | null = null,
) {
  return useQuery({
    queryKey: ["alerts", filters, severity, category],
    queryFn: () =>
      apiGet<AlertsResponse>("/alerts", {
        ...filterParamsRecord(filters),
        severity,
        category,
      }),
    placeholderData: keepPreviousData,
  });
}

export async function askAnalyst(
  question: string,
  filters: GlobalFilterParams,
): Promise<AnalystResponse> {
  return apiPost<AnalystResponse>("/analyst/ask", { question, filters });
}

export function useBackgroundPrefetch() {
  useEffect(() => {
    const timer = window.setTimeout(() => {
      const defaults: GlobalFilterParams = {
        start_date: DB_MIN_DATE,
        end_date: DB_MAX_DATE,
        region_id: null,
        store_id: null,
        category_id: null,
        subcategory_id: null,
      };
      const base = filterParamsRecord(defaults);
      void queryClient.prefetchQuery({
        queryKey: ["alerts", defaults, null, null],
        queryFn: () => apiGet<AlertsResponse>("/alerts", base),
      });
      void queryClient.prefetchQuery({
        queryKey: ["stores", defaults, "attainment_pct"],
        queryFn: () => apiGet<StoresResponse>("/stores", { ...base, sort_by: "attainment_pct" }),
      });
      void queryClient.prefetchQuery({
        queryKey: ["promotions", defaults],
        queryFn: () => apiGet<PromotionsResponse>("/promotions", base),
      });
      void queryClient.prefetchQuery({
        queryKey: ["inventory", null, null, null, null, 50],
        queryFn: () => apiGet<InventoryResponse>("/inventory", { limit: 50 }),
      });
      void queryClient.prefetchQuery({
        queryKey: ["customers", defaults],
        queryFn: () => apiGet<CustomersResponse>("/customers", base),
      });
    }, 200);
    return () => window.clearTimeout(timer);
  }, []);
}
