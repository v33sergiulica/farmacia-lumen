import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { queryClient } from "./api/client";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { Layout } from "./components/Layout";
import { FilterProvider } from "./context/FilterContext";
import { ActionsPage } from "./pages/ActionsPage";
import { CustomersPage } from "./pages/CustomersPage";
import { InventoryPage } from "./pages/InventoryPage";
import { OverviewPage } from "./pages/OverviewPage";
import { PromotionsPage } from "./pages/PromotionsPage";
import { StoresPage } from "./pages/StoresPage";

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <FilterProvider>
          <Layout>
            <ErrorBoundary>
              <Routes>
                <Route path="/" element={<OverviewPage />} />
                <Route path="/stores" element={<StoresPage />} />
                <Route path="/promotions" element={<PromotionsPage />} />
                <Route path="/inventory" element={<InventoryPage />} />
                <Route path="/customers" element={<CustomersPage />} />
                <Route path="/actions" element={<ActionsPage />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </ErrorBoundary>
          </Layout>
        </FilterProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
