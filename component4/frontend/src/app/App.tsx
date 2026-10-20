import { Routes, Route, Navigate } from "react-router-dom";
import { AppShell } from "../layout/AppShell";
import { OverviewPage } from "../features/overview/OverviewPage";
import { SortingSystemPage } from "../features/sorting/SortingSystemPage";
import { GloveOrientationPage } from "../features/orientation/GloveOrientationPage";
import {
  AlertsPage, BatchesPage, DataManagementPage, DefectsPage, HistoryPage,
  PredictionsPage, ProductionPage, ReportsPage, SettingsPage,
} from "../features/workspace/WorkspacePages";

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<OverviewPage />} />
        <Route path="/production" element={<ProductionPage />} />
        <Route path="/sorting-system" element={<SortingSystemPage />} />
        <Route path="/live-orientation" element={<GloveOrientationPage />} />
        <Route path="/defects" element={<DefectsPage />} />
        <Route path="/batches" element={<BatchesPage />} />
        <Route path="/predictions" element={<PredictionsPage />} />
        <Route path="/alerts" element={<AlertsPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/data-management" element={<DataManagementPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
