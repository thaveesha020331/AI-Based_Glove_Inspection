import { useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Bell, Camera, ChevronDown, Factory, Menu, RadioTower, Search, X } from "lucide-react";

const navigation = [
  { label: "Overview", path: "/", icon: "◈" }, { label: "Production Analytics", path: "/production", icon: "▥" },
  { label: "Sorting System", path: "/sorting-system", icon: <RadioTower size={16} /> },
  { label: "Live Orientation", path: "/live-orientation", icon: <Camera size={16} /> },
  { label: "Defect Analysis", path: "/defects", icon: "◌" }, { label: "Batch Quality", path: "/batches", icon: "✓" },
  { label: "Predictive Analytics", path: "/predictions", icon: "⌁" }, { label: "Alerts & Recommendations", path: "/alerts", icon: "!" },
  { label: "Reports", path: "/reports", icon: "▤" }, { label: "Historical Records", path: "/history", icon: "◷" },
  { label: "Data Management", path: "/data-management", icon: "⇅" }, { label: "Settings", path: "/settings", icon: "⚙" },
];

export function AppShell() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const current = navigation.find((item) => item.path === location.pathname)?.label ?? "Overview";
  return (
    <div className="min-h-screen bg-canvas">
      <aside className={`fixed inset-y-0 left-0 z-40 flex w-[256px] flex-col border-r border-line bg-white transition-transform lg:translate-x-0 ${mobileOpen ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="flex h-[76px] items-center justify-between border-b border-line px-6">
          <div className="flex items-center gap-3"><div className="grid h-9 w-9 place-items-center rounded-xl bg-ink text-white"><Factory size={18} /></div><div><p className="heading text-[15px] font-extrabold tracking-tight">Glove<span className="text-brand">IQ</span></p><p className="text-[10px] font-semibold uppercase tracking-[.16em] text-muted">Quality intelligence</p></div></div>
          <button className="focus-ring rounded-lg p-1 text-muted lg:hidden" onClick={() => setMobileOpen(false)} aria-label="Close navigation"><X size={20} /></button>
        </div>
        <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-5" aria-label="Primary navigation">
          <p className="px-3 pb-3 text-[10px] font-bold uppercase tracking-[.18em] text-slate-400">Workspace</p>
          {navigation.map((item) => <NavLink key={item.path} to={item.path} end={item.path === "/"} onClick={() => setMobileOpen(false)} className={({ isActive }) => `group flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-semibold transition-colors ${isActive ? "bg-[#edf5f8] text-brand" : "text-muted hover:bg-slate-50 hover:text-ink"}`}><span className="grid w-5 place-items-center text-[16px] opacity-80">{item.icon}</span>{item.label}</NavLink>)}
        </nav>
        <div className="m-3 rounded-xl bg-[#f3f7f8] p-3"><p className="text-xs font-bold text-ink">Demo workspace</p><p className="mt-1 text-[11px] leading-4 text-muted">Figures are sample data for development.</p></div>
      </aside>
      {mobileOpen && <button className="fixed inset-0 z-30 bg-ink/30 lg:hidden" onClick={() => setMobileOpen(false)} aria-label="Close navigation overlay" />}
      <div className="lg:pl-[256px]">
        <header className="sticky top-0 z-20 flex h-[76px] items-center justify-between border-b border-line bg-white/95 px-5 backdrop-blur lg:px-8">
          <div className="flex items-center gap-3"><button className="focus-ring rounded-lg p-2 text-muted hover:bg-slate-50 lg:hidden" onClick={() => setMobileOpen(true)} aria-label="Open navigation"><Menu size={21} /></button><div><div className="hidden items-center gap-2 text-xs text-muted sm:flex"><span>Workspace</span><span>/</span><span className="text-ink">{current}</span></div><h1 className="heading text-lg font-bold text-ink sm:mt-1 sm:text-xl">{current}</h1></div></div>
          <div className="flex items-center gap-2 sm:gap-4"><button onClick={() => navigate("/alerts")} className="focus-ring hidden items-center gap-2 rounded-lg border border-line bg-slate-50 px-3 py-2 text-xs text-muted md:flex" aria-label="Open alerts"><Search size={15} /><span>Search alerts</span><kbd className="ml-5 rounded border border-line bg-white px-1.5 py-0.5 text-[10px]">⌘ K</kbd></button><button onClick={() => navigate("/alerts")} className="focus-ring relative rounded-lg p-2 text-muted hover:bg-slate-50" aria-label="Open notifications"><Bell size={19} /><span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-red-500" /></button><div className="hidden h-8 w-px bg-line sm:block" /><button onClick={() => navigate("/settings")} className="focus-ring flex items-center gap-2 rounded-lg p-1.5 hover:bg-slate-50" aria-label="Open settings"><div className="grid h-8 w-8 place-items-center rounded-full bg-[#dcecf1] text-xs font-bold text-brand">AT</div><span className="hidden text-left text-xs sm:block"><span className="block font-bold text-ink">Alex Taylor</span><span className="block text-muted">Quality lead</span></span><ChevronDown size={14} className="hidden text-muted sm:block" /></button></div>
        </header>
        <div className="border-b border-line bg-[#fbfcfd] px-5 py-2.5 text-xs text-muted lg:px-8"><span className="font-semibold text-teal">LIVE API WORKSPACE</span><span className="mx-2 text-slate-300">•</span>Metrics and predictions are loaded from the configured Flask data source.</div>
        <Outlet />
      </div>
    </div>
  );
}
