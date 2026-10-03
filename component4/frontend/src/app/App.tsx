import { Routes, Route, Navigate } from "react-router-dom";
import { AppShell } from "../layout/AppShell";
import { OverviewPage } from "../features/overview/OverviewPage";

const pages = [
  ["production", "Production Analytics"], ["defects", "Defect Analysis"], ["batches", "Batch Quality"],
  ["predictions", "Predictive Analytics"], ["alerts", "Alerts & Recommendations"], ["reports", "Reports"],
  ["history", "Historical Records"], ["data-management", "Data Management"], ["settings", "Settings"],
];

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<OverviewPage />} />
        {pages.map(([path, title]) => <Route key={path} path={`/${path}`} element={<PlaceholderPage title={title} />} />)}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

function PlaceholderPage({ title }: { title: string }) {
  return <main className="p-6 lg:p-8"><div className="rounded-2xl border border-line bg-white p-10 text-center shadow-soft"><p className="text-sm font-semibold uppercase tracking-[.14em] text-brand">Coming next</p><h1 className="heading mt-3 text-3xl font-bold">{title}</h1><p className="mx-auto mt-3 max-w-md text-muted">This domain workspace is wired into the navigation and ready for its analytics view.</p></div></main>;
}
