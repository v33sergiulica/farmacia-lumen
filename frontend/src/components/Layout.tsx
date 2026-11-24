import { useIsFetching } from "@tanstack/react-query";
import {
  AlertTriangle,
  BarChart3,
  Building2,
  Menu,
  MessageSquareCode,
  Package,
  Percent,
  Users,
  X,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useAlerts, useBackgroundPrefetch } from "../api/client";
import { useFilters } from "../context/FilterContext";
import { AnalystDrawer } from "./AnalystDrawer";
import { FilterBar } from "./FilterBar";

interface NavItem {
  to: string;
  label: string;
  icon: typeof BarChart3;
  title: string;
}

const NAV_ITEMS: NavItem[] = [
  {
    to: "/",
    label: "Executive Overview",
    icon: BarChart3,
    title: "Executive Overview",
  },
  {
    to: "/stores",
    label: "Stores & Regions",
    icon: Building2,
    title: "Stores & Regional Performance",
  },
  {
    to: "/promotions",
    label: "Promotions & Margin",
    icon: Percent,
    title: "Promotions & Margin Lab",
  },
  {
    to: "/inventory",
    label: "Inventory & Restock",
    icon: Package,
    title: "Inventory & Restock Risk",
  },
  {
    to: "/customers",
    label: "Customers & Loyalty",
    icon: Users,
    title: "Customers & Loyalty Insights",
  },
  {
    to: "/actions",
    label: "Actions & Alerts",
    icon: AlertTriangle,
    title: "Operational Problems & Recommended Actions",
  },
];

export function Layout({ children }: { children: ReactNode }) {
  useBackgroundPrefetch();
  const isFetching = useIsFetching();
  const location = useLocation();
  const { filters } = useFilters();
  const { data: alertsData } = useAlerts(filters);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  const urgentCount = alertsData
    ? alertsData.counts.critical + alertsData.counts.high
    : null;

  const currentPage =
    NAV_ITEMS.find((n) => n.to === location.pathname) ?? NAV_ITEMS[0];

  const sidebarContent = (
    <div className="flex h-full flex-col justify-between bg-white">
      <div>
        <div className="border-b border-[#E2E7E4] px-5 py-4">
          <div className="text-sm font-semibold tracking-tight text-[#111A16]">
            Farmacia Lumen
          </div>
          <div className="mt-0.5 text-xs text-[#5C6B63]">
            Executive BI &amp; Operations
          </div>
        </div>
        <nav className="space-y-1 p-3" aria-label="Primary navigation">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={`${item.to}${location.search}`}
                end={item.to === "/"}
                onClick={() => setMobileNavOpen(false)}
                className={({ isActive }) =>
                  `flex items-center justify-between rounded-md px-3 py-2 text-[13px] font-medium transition-colors ${
                    isActive
                      ? "bg-[#ECF6F0] text-[#146C43]"
                      : "text-[#46544D] hover:bg-[#F6F7F6] hover:text-[#111A16]"
                  }`
                }
              >
                <span className="flex items-center gap-2.5">
                  <Icon size={16} strokeWidth={1.5} />
                  <span>{item.label}</span>
                </span>
                {item.to === "/actions" && urgentCount !== null && urgentCount > 0 && (
                  <span className="tabular rounded bg-[#FEF3F2] px-1.5 py-0.5 text-[11px] font-semibold text-[#B42318]">
                    {urgentCount}
                  </span>
                )}
              </NavLink>
            );
          })}
        </nav>
      </div>

      <div className="border-t border-[#E2E7E4] px-5 py-3.5 text-xs text-[#5C6B63]">
        <div>All values: RON (fără TVA)</div>
        <div className="font-mono-data mt-0.5 text-[11px]">
          21 stores · 2025-05 – 2026-10
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex min-h-screen bg-[#F6F7F6] text-[#111A16]">
      {/* Top subtle loading indicator */}
      <div className="pointer-events-none fixed inset-x-0 top-0 z-50 h-0.5 overflow-hidden">
        {isFetching > 0 && (
          <div className="animate-top-progress h-full w-1/3 bg-[#146C43]" />
        )}
      </div>

      {/* Desktop Sidebar */}
      <aside className="hidden w-60 shrink-0 border-r border-[#E2E7E4] bg-white lg:block">
        <div className="sticky top-0 h-screen">{sidebarContent}</div>
      </aside>

      {/* Mobile Sidebar Overlay */}
      {mobileNavOpen && (
        <div className="fixed inset-0 z-40 flex lg:hidden">
          <div
            className="fixed inset-0 bg-[#111A16]/25"
            onClick={() => setMobileNavOpen(false)}
          />
          <aside className="relative z-10 w-64 border-r border-[#E2E7E4] bg-white">
            <button
              type="button"
              onClick={() => setMobileNavOpen(false)}
              aria-label="Close navigation"
              className="absolute right-3 top-3 rounded p-1 text-[#5C6B63] hover:bg-[#F6F7F6]"
            >
              <X size={16} strokeWidth={1.5} />
            </button>
            {sidebarContent}
          </aside>
        </div>
      )}

      {/* Main Content Column */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-[#E2E7E4] bg-white px-4 py-3 lg:px-6">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setMobileNavOpen(true)}
              aria-label="Open navigation"
              className="rounded-md border border-[#E2E7E4] p-1.5 text-[#46544D] lg:hidden"
            >
              <Menu size={16} strokeWidth={1.5} />
            </button>
            <div>
              <h1 className="text-balance text-base font-semibold tracking-tight text-[#111A16] sm:text-lg">
                {currentPage.title}
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <span className="hidden text-xs font-medium text-[#5C6B63] sm:inline">
              Monetary basis: RON (fără TVA)
            </span>
            <button
              type="button"
              onClick={() => setDrawerOpen(true)}
              className="inline-flex items-center gap-1.5 rounded-md bg-[#146C43] px-3.5 py-2 text-xs font-medium text-white transition-colors hover:bg-[#0F5132]"
            >
              <MessageSquareCode size={15} strokeWidth={1.5} />
              Ask Your Data
            </button>
          </div>
        </header>

        <FilterBar />

        <main className="mx-auto w-full max-w-[1440px] flex-1 p-4 lg:p-6">
          {children}
        </main>
      </div>

      <AnalystDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />
    </div>
  );
}
