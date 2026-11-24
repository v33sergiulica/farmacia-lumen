import { RotateCcw } from "lucide-react";
import { useEffect, useMemo, useState, type KeyboardEvent } from "react";
import { useFiltersMeta } from "../api/client";
import { useFilters } from "../context/FilterContext";
import { DATE_PRESETS, DB_MAX_DATE, DB_MIN_DATE, shortStoreName } from "../utils/format";

const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

function isValidBoundedDate(value: string): boolean {
  if (!ISO_DATE_RE.test(value)) return false;
  if (value < DB_MIN_DATE || value > DB_MAX_DATE) return false;
  const [y, m, d] = value.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  return (
    dt.getUTCFullYear() === y &&
    dt.getUTCMonth() === m - 1 &&
    dt.getUTCDate() === d
  );
}

export function FilterBar() {
  const { filters, hasActiveFilters, setFilter, resetFilters } = useFilters();
  const { data: meta } = useFiltersMeta();

  const [draftStart, setDraftStart] = useState(filters.start_date);
  const [draftEnd, setDraftEnd] = useState(filters.end_date);

  useEffect(() => {
    setDraftStart(filters.start_date);
  }, [filters.start_date]);

  useEffect(() => {
    setDraftEnd(filters.end_date);
  }, [filters.end_date]);

  function commitStart(candidate: string) {
    if (isValidBoundedDate(candidate) && candidate <= filters.end_date) {
      if (candidate !== filters.start_date) {
        setFilter({ start_date: candidate });
      }
    } else {
      setDraftStart(filters.start_date);
    }
  }

  function commitEnd(candidate: string) {
    if (isValidBoundedDate(candidate) && candidate >= filters.start_date) {
      if (candidate !== filters.end_date) {
        setFilter({ end_date: candidate });
      }
    } else {
      setDraftEnd(filters.end_date);
    }
  }

  function handleKeyDown(
    e: KeyboardEvent<HTMLInputElement>,
    commitFn: () => void,
  ) {
    if (e.key === "Enter") {
      commitFn();
    }
  }

  const activePresetId = useMemo(() => {
    const match = DATE_PRESETS.find(
      (p) => p.start_date === filters.start_date && p.end_date === filters.end_date,
    );
    return match ? match.id : null;
  }, [filters.start_date, filters.end_date]);

  const filteredStores = useMemo(() => {
    if (!meta) return [];
    if (filters.region_id === null) return meta.stores;
    return meta.stores.filter((s) => s.id_regiune === filters.region_id);
  }, [meta, filters.region_id]);

  const subcategories = useMemo(() => {
    if (!meta || filters.category_id === null) return [];
    const cat = meta.categories.find((c) => c.id === filters.category_id);
    return cat ? cat.subcategories : [];
  }, [meta, filters.category_id]);

  return (
    <div className="sticky top-0 z-20 border-b border-[#E2E7E4] bg-white px-4 py-2.5 lg:px-6">
      <div className="flex flex-wrap items-center gap-2.5">
        {/* Anchored Date Presets (concentric p-1 rounded-lg -> rounded) */}
        <div
          className="inline-flex items-center rounded-lg border border-[#E2E7E4] bg-[#F6F7F6] p-1"
          role="group"
          aria-label="Date range presets"
        >
          {DATE_PRESETS.map((preset) => {
            const active = activePresetId === preset.id;
            return (
              <button
                key={preset.id}
                type="button"
                onClick={() =>
                  setFilter({
                    start_date: preset.start_date,
                    end_date: preset.end_date,
                  })
                }
                className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                  active
                    ? "bg-white text-[#146C43] ring-1 ring-[#E2E7E4]"
                    : "text-[#46544D] hover:text-[#111A16]"
                }`}
              >
                {preset.label}
              </button>
            );
          })}
        </div>

        {/* Exact Date Inputs (local draft; commits only valid in-bounds dates) */}
        <div className="flex items-center gap-1.5 text-xs">
          <input
            type="date"
            aria-label="Start date"
            min={DB_MIN_DATE}
            max={DB_MAX_DATE}
            value={draftStart}
            onChange={(e) => {
              const val = e.target.value;
              setDraftStart(val);
              if (isValidBoundedDate(val) && val <= filters.end_date) {
                setFilter({ start_date: val });
              }
            }}
            onBlur={() => commitStart(draftStart)}
            onKeyDown={(e) => handleKeyDown(e, () => commitStart(draftStart))}
            className="font-mono-data h-8 rounded-md border border-[#E2E7E4] bg-white px-2 text-xs text-[#111A16] focus:border-[#146C43] focus:outline-none"
          />
          <span className="text-[#5C6B63]">to</span>
          <input
            type="date"
            aria-label="End date"
            min={DB_MIN_DATE}
            max={DB_MAX_DATE}
            value={draftEnd}
            onChange={(e) => {
              const val = e.target.value;
              setDraftEnd(val);
              if (isValidBoundedDate(val) && val >= filters.start_date) {
                setFilter({ end_date: val });
              }
            }}
            onBlur={() => commitEnd(draftEnd)}
            onKeyDown={(e) => handleKeyDown(e, () => commitEnd(draftEnd))}
            className="font-mono-data h-8 rounded-md border border-[#E2E7E4] bg-white px-2 text-xs text-[#111A16] focus:border-[#146C43] focus:outline-none"
          />
        </div>

        {/* Region Select */}
        <select
          aria-label="Region"
          value={filters.region_id ?? ""}
          onChange={(e) => {
            const val = e.target.value ? Number(e.target.value) : null;
            const keepStore =
              val === null ||
              (filters.store_id !== null &&
                meta?.stores.some((s) => s.id === filters.store_id && s.id_regiune === val));
            setFilter({
              region_id: val,
              store_id: keepStore ? filters.store_id : null,
            });
          }}
          className="h-8 rounded-md border border-[#E2E7E4] bg-white px-2.5 text-xs text-[#111A16] focus:border-[#146C43] focus:outline-none"
        >
          <option value="">All Regions (8)</option>
          {meta?.regions.map((r) => (
            <option key={r.id} value={r.id}>
              {r.nume}
            </option>
          ))}
        </select>

        {/* Pharmacy Select */}
        <select
          aria-label="Pharmacy"
          value={filters.store_id ?? ""}
          onChange={(e) =>
            setFilter({ store_id: e.target.value ? Number(e.target.value) : null })
          }
          className="h-8 max-w-[210px] rounded-md border border-[#E2E7E4] bg-white px-2.5 text-xs text-[#111A16] focus:border-[#146C43] focus:outline-none"
        >
          <option value="">All Pharmacies ({filteredStores.length || 21})</option>
          {filteredStores.map((s) => (
            <option key={s.id} value={s.id}>
              #{s.id} {shortStoreName(s.nume)}
              {s.status === "closed" ? " (Closed)" : ""}
            </option>
          ))}
        </select>

        {/* Category L1 Select */}
        <select
          aria-label="Category"
          value={filters.category_id ?? ""}
          onChange={(e) =>
            setFilter({
              category_id: e.target.value ? Number(e.target.value) : null,
            })
          }
          className="h-8 rounded-md border border-[#E2E7E4] bg-white px-2.5 text-xs text-[#111A16] focus:border-[#146C43] focus:outline-none"
        >
          <option value="">All Categories (6)</option>
          {meta?.categories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.nume}
            </option>
          ))}
        </select>

        {/* Subcategory L2 Select (visible when L1 selected) */}
        {filters.category_id !== null && subcategories.length > 0 && (
          <select
            aria-label="Subcategory"
            value={filters.subcategory_id ?? ""}
            onChange={(e) =>
              setFilter({
                subcategory_id: e.target.value ? Number(e.target.value) : null,
              })
            }
            className="h-8 rounded-md border border-[#E2E7E4] bg-white px-2.5 text-xs text-[#111A16] focus:border-[#146C43] focus:outline-none"
          >
            <option value="">All Subcategories ({subcategories.length})</option>
            {subcategories.map((sc) => (
              <option key={sc.id} value={sc.id}>
                {sc.nume}
              </option>
            ))}
          </select>
        )}

        {hasActiveFilters && (
          <button
            type="button"
            onClick={resetFilters}
            className="inline-flex h-8 items-center gap-1 rounded-md px-2 text-xs font-medium text-[#5C6B63] hover:bg-[#F6F7F6] hover:text-[#111A16]"
          >
            <RotateCcw size={13} strokeWidth={1.5} />
            Reset
          </button>
        )}
      </div>
    </div>
  );
}
