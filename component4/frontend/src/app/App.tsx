import { Routes, Route, Navigate } from "react-router-dom";
import { AppShell } from "../layout/AppShell";
import { OverviewPage } from "../features/overview/OverviewPage";
import { SortingControlPage } from "../features/sorting/SortingControlPage";
import { GloveOrientationPage } from "../features/orientation/GloveOrientationPage";
import { LiveDefectDetectionPage } from "../features/defects/LiveDefectDetectionPage";
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
        <Route path="/sorting-system" element={<SortingControlPage />} />
        <Route path="/live-orientation" element={<GloveOrientationPage />} />
        <Route path="/live-defects" element={<LiveDefectDetectionPage />} />
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
