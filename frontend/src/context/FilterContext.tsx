import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  type ReactNode,
} from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import type { GlobalFilterParams } from "../types/api";
import { DB_MAX_DATE, DB_MIN_DATE } from "../utils/format";

interface FilterContextValue {
  filters: GlobalFilterParams;
  hasActiveFilters: boolean;
  setFilter: (patch: Partial<GlobalFilterParams>) => void;
  resetFilters: () => void;
  navigateWithFilters: (path: string, patch?: Record<string, string | number>) => void;
}

const FilterContext = createContext<FilterContextValue | null>(null);

function parseIntParam(raw: string | null): number | null {
  if (!raw) return null;
  const num = Number.parseInt(raw, 10);
  return Number.isFinite(num) && num > 0 ? num : null;
}

export function FilterProvider({ children }: { children: ReactNode }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const filters: GlobalFilterParams = useMemo(
    () => ({
      start_date: searchParams.get("start_date") || DB_MIN_DATE,
      end_date: searchParams.get("end_date") || DB_MAX_DATE,
      region_id: parseIntParam(searchParams.get("region_id")),
      store_id: parseIntParam(searchParams.get("store_id")),
      category_id: parseIntParam(searchParams.get("category_id")),
      subcategory_id: parseIntParam(searchParams.get("subcategory_id")),
    }),
    [searchParams],
  );

  const hasActiveFilters = useMemo(
    () =>
      filters.start_date !== DB_MIN_DATE ||
      filters.end_date !== DB_MAX_DATE ||
      filters.region_id !== null ||
      filters.store_id !== null ||
      filters.category_id !== null ||
      filters.subcategory_id !== null,
    [filters],
  );

  const buildSearchParams = useCallback((next: GlobalFilterParams) => {
    const sp = new URLSearchParams();
    if (next.start_date && next.start_date !== DB_MIN_DATE) sp.set("start_date", next.start_date);
    if (next.end_date && next.end_date !== DB_MAX_DATE) sp.set("end_date", next.end_date);
    if (next.region_id !== null) sp.set("region_id", String(next.region_id));
    if (next.store_id !== null) sp.set("store_id", String(next.store_id));
    if (next.category_id !== null) sp.set("category_id", String(next.category_id));
    if (next.subcategory_id !== null) sp.set("subcategory_id", String(next.subcategory_id));
    return sp;
  }, []);

  const setFilter = useCallback(
    (patch: Partial<GlobalFilterParams>) => {
      const next: GlobalFilterParams = { ...filters, ...patch };
      if ("category_id" in patch && patch.category_id !== filters.category_id) {
        next.subcategory_id = null;
      }
      setSearchParams(buildSearchParams(next), { replace: true });
    },
    [filters, setSearchParams, buildSearchParams],
  );

  const resetFilters = useCallback(() => {
    setSearchParams(new URLSearchParams(), { replace: true });
  }, [setSearchParams]);

  const navigateWithFilters = useCallback(
    (path: string, patch: Record<string, string | number> = {}) => {
      const next: GlobalFilterParams = { ...filters };
      if ("store_id" in patch) next.store_id = Number(patch.store_id);
      if ("region_id" in patch) next.region_id = Number(patch.region_id);
      if ("category_id" in patch) next.category_id = Number(patch.category_id);
      if ("subcategory_id" in patch) next.subcategory_id = Number(patch.subcategory_id);
      if ("start_date" in patch) next.start_date = String(patch.start_date);
      if ("end_date" in patch) next.end_date = String(patch.end_date);
      const sp = buildSearchParams(next);
      const qs = sp.toString();
      navigate(qs ? `${path}?${qs}` : path);
    },
    [filters, buildSearchParams, navigate],
  );

  const value = useMemo(
    () => ({
      filters,
      hasActiveFilters,
      setFilter,
      resetFilters,
      navigateWithFilters,
    }),
    [filters, hasActiveFilters, setFilter, resetFilters, navigateWithFilters],
  );

  return <FilterContext.Provider value={value}>{children}</FilterContext.Provider>;
}

export function useFilters(): FilterContextValue {
  const ctx = useContext(FilterContext);
  if (!ctx) throw new Error("useFilters must be used inside FilterProvider");
  return ctx;
}
