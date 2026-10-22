import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, ArrowRight, CheckCircle2, RefreshCw, ShieldAlert } from "lucide-react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { apiData, apiMessage } from "../../services/api";

type State<T> = { data: T | null; loading: boolean; error: string | null };
type Summary = { production_quantity: number | null; inspected_quantity: number | null; accepted_quantity: number | null; rejected_quantity: number | null; rejection_rate: number | null; inspection_coverage: number | null; batch_count: number; data_quality_warnings: unknown[] };
type Trend = { date?: string; period?: string; production_quantity?: number; rejected_quantity?: number; rejection_rate?: number };
type Descriptive = { defects: { frequency_by_category: { defect_category: string; count: number }[] }; quality: { grade_distribution: Record<string, number> }; batch_summaries: Record<string, unknown>[] };
type Alert = { id: number; title: string; description: string; severity: string; batch_id?: string; created_at: string; status: string };
type PredictionAnalytics = { risk_distribution: Record<string, number> };

function useData<T>(url: string, refresh: number): State<T> {
  const [state, setState] = useState<State<T>>({ data: null, loading: true, error: null });
  useEffect(() => {
    let active = true;
    setState({ data: null, loading: true, error: null });
    apiData<T>({ url }).then((data) => active && setState({ data, loading: false, error: null }))
      .catch((error: unknown) => active && setState({ data: null, loading: false, error: apiMessage(error) }));
    return () => { active = false; };
  }, [url, refresh]);
  return state;
}

function format(value: unknown) {
  return value === null || value === undefined ? "—" : typeof value === "number" ? value.toLocaleString(undefined, { maximumFractionDigits: 2 }) : String(value);
}

function Panel({ title, subtitle, children, link }: { title: string; subtitle: string; children: React.ReactNode; link?: string }) {
  return <section className="surface-glow min-w-0 rounded-2xl border border-line p-5 shadow-soft transition-shadow hover:shadow-[0_12px_34px_rgba(19,34,56,.09)] sm:p-6"><div className="flex items-start justify-between gap-3"><div><h3 className="heading text-sm font-bold text-ink">{title}</h3><p className="mt-1 text-xs text-muted">{subtitle}</p></div>{link && <Link className="flex shrink-0 items-center gap-1 text-xs font-bold text-brand" to={link}>View <ArrowRight size={13} /></Link>}</div><div className="mt-5">{children}</div></section>;
}

function Stat({ label, value, detail, tone = "blue" }: { label: string; value: unknown; detail: string; tone?: "blue" | "green" | "red" | "amber" }) {
  const color = { blue: "text-brand", green: "text-[#18815c]", red: "text-red-500", amber: "text-amber-600" }[tone];
  return <div className="surface-glow relative overflow-hidden rounded-2xl border border-line p-4 shadow-soft"><span className={`absolute left-0 top-0 h-full w-1 ${tone === "red" ? "bg-red-400" : tone === "green" ? "bg-teal" : tone === "amber" ? "bg-amber-400" : "bg-brand"}`} /><p className="pl-2 text-xs font-semibold text-muted">{label}</p><p className={`heading mt-2 pl-2 text-2xl font-extrabold ${color}`}>{format(value)}</p><p className="mt-1 pl-2 text-[11px] text-muted">{detail}</p></div>;
}

function Failure({ message, retry }: { message: string; retry: () => void }) {
  return <div className="rounded-xl border border-[#f1d4d1] bg-[#fff8f7] p-5 text-sm text-red-600"><AlertTriangle className="mr-2 inline-block" size={16} />{message}<button onClick={retry} className="ml-3 rounded-lg border border-[#e7b9b5] px-3 py-1 text-xs font-bold">Retry</button></div>;
}

export function OverviewPage() {
  const [refresh, setRefresh] = useState(0);
  const summary = useData<Summary>("/dashboard/summary", refresh);
  const descriptive = useData<Descriptive>("/analytics/descriptive", refresh);
  const trends = useData<Trend[]>("/analytics/trends?granularity=daily", refresh);
  const alerts = useData<Alert[]>("/alerts?status=Open&per_page=5", refresh);
  const predictions = useData<PredictionAnalytics>("/predictions/analytics", refresh);
  const synthetic = useData<Record<string, unknown>>("/analytics/synthetic", refresh);
  const error = [summary, descriptive, trends, alerts, predictions, synthetic].find((item) => item.error);
  if (error?.error) return <main className="page-grid min-h-[calc(100vh-76px)] p-5 lg:p-8"><div className="mx-auto max-w-[1500px]"><Failure message={error.error} retry={() => setRefresh((value) => value + 1)} /></div></main>;
  const kpis = summary.data;
  const riskCount = Object.entries(predictions.data?.risk_distribution ?? {}).filter(([key]) => key.toLowerCase() === "high").reduce((total, [, value]) => total + value, 0);
  return <main className="page-grid min-h-[calc(100vh-76px)] p-4 sm:p-5 lg:p-8"><div className="mx-auto max-w-[1500px]">
    <div className="surface-glow relative mb-5 overflow-hidden rounded-3xl border border-line p-5 shadow-soft sm:p-7"><div className="absolute -right-16 -top-24 h-64 w-64 rounded-full bg-brand/10 blur-2xl" /><div className="relative flex flex-col justify-between gap-5 md:flex-row md:items-end"><div><p className="text-xs font-bold uppercase tracking-[.18em] text-brand">Live workspace</p><h2 className="heading mt-2 max-w-2xl text-3xl font-extrabold tracking-tight text-ink sm:text-4xl">Quality intelligence at a glance.</h2><p className="mt-2 max-w-xl text-sm leading-6 text-muted">A focused view of production health, inspection signals, and predictive risk across your operation.</p></div><button onClick={() => setRefresh((value) => value + 1)} className="focus-ring flex w-fit items-center gap-2 rounded-xl bg-ink px-4 py-2.5 text-xs font-bold text-white shadow-lg shadow-ink/10 transition-transform hover:-translate-y-0.5"><RefreshCw size={14} /> Refresh data</button></div><div className="relative mt-6 flex flex-wrap gap-2 text-[11px] font-semibold text-muted"><span className="rounded-full bg-[#e8f6f0] px-3 py-1.5 text-[#18815c]">● API connected</span><span className="rounded-full bg-[#edf5f8] px-3 py-1.5 text-brand">{format(kpis?.batch_count)} batches tracked</span><span className="rounded-full bg-slate-100 px-3 py-1.5">Updated just now</span></div></div>
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3"><Stat label="Total production" value={kpis?.production_quantity} detail="database quantity" /><Stat label="Inspected quantity" value={kpis?.inspected_quantity} detail={`${format(kpis?.inspection_coverage)}% database coverage`} tone="green" /><Stat label="Accepted gloves" value={kpis?.accepted_quantity} detail="database accepted quantity" tone="green" /><Stat label="Rejected gloves" value={kpis?.rejected_quantity} detail={`${format(kpis?.rejection_rate)}% database rejection rate`} tone="red" /><Stat label="Batches" value={kpis?.batch_count} detail="database batches" /><Stat label="High-risk predictions" value={riskCount} detail="persisted model predictions" tone="amber" /></div>
    <div className="mt-5 rounded-2xl border border-[#d8e8ed] bg-[#f3f9fa] p-4"><p className="text-xs font-bold text-brand">Synthetic model dataset</p><p className="mt-1 text-xs text-muted">{String(synthetic.data?.source ?? "Loading synthetic dataset summary…")}</p><div className="mt-3 grid gap-3 sm:grid-cols-4"><Stat label="CSV batches" value={synthetic.data?.batch_count} detail="training rows" /><Stat label="CSV accepted" value={(synthetic.data?.totals as Record<string, unknown> | undefined)?.total_accepted} detail="synthetic quantity" tone="green" /><Stat label="CSV rejected" value={(synthetic.data?.totals as Record<string, unknown> | undefined)?.total_rejected} detail="synthetic quantity" tone="red" /><Stat label="CSV high risk" value={(synthetic.data?.risk_distribution as Record<string, unknown> | undefined)?.High} detail="label distribution" tone="amber" /></div></div>
    <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1.55fr)_minmax(320px,.8fr)]"><Panel title="Production and rejection trend" subtitle="Values are calculated from production records" link="/production"><div className="h-[280px]"><ResponsiveContainer width="100%" height="100%"><AreaChart data={trends.data ?? []} margin={{ left: -15, right: 8, top: 10 }}><CartesianGrid vertical={false} stroke="#edf0f4" /><XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fill: "#8a97a9", fontSize: 11 }} /><YAxis axisLine={false} tickLine={false} tick={{ fill: "#8a97a9", fontSize: 11 }} /><Tooltip /><Area type="monotone" dataKey="production_quantity" name="Production" stroke="#1d6b8f" fill="#dcecf1" strokeWidth={2.5} /><Area type="monotone" dataKey="rejected_quantity" name="Rejected" stroke="#d65b5b" fill="none" strokeWidth={2} /></AreaChart></ResponsiveContainer></div></Panel>
      <Panel title="Defect distribution" subtitle="Recorded defect events by category" link="/defects"><div className="space-y-3">{(descriptive.data?.defects.frequency_by_category ?? []).slice(0, 6).map((item) => <div key={item.defect_category} className="flex items-center justify-between gap-3 text-xs"><span className="min-w-0 truncate text-muted">{item.defect_category}</span><b className="text-ink">{format(item.count)}</b></div>)}{!descriptive.data?.defects.frequency_by_category.length && <p className="text-sm text-muted">No defect records are available.</p>}</div></Panel></div>
    <div className="mt-5 grid gap-5 lg:grid-cols-[.85fr_1.15fr]"><Panel title="Quality grades" subtitle="Persisted quality record distribution" link="/batches"><div className="grid grid-cols-2 gap-3">{Object.entries(descriptive.data?.quality.grade_distribution ?? {}).map(([grade, count]) => <div key={grade} className="rounded-xl bg-[#f3f7f8] p-3"><p className="text-xs text-muted">{grade}</p><p className="heading mt-1 text-xl font-extrabold text-ink">{format(count)}</p></div>)}</div></Panel><Panel title="Latest quality alerts" subtitle="Open alerts requiring attention" link="/alerts"><div className="space-y-1">{(alerts.data ?? []).map((alert) => <div key={alert.id} className="flex gap-3 border-b border-slate-100 py-3 last:border-0"><div className={`mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg ${alert.severity === "critical" || alert.severity === "high" ? "bg-[#fff0ef] text-red-500" : "bg-[#fff5df] text-amber-600"}`}><ShieldAlert size={16} /></div><div className="min-w-0 flex-1"><div className="flex justify-between gap-2"><p className="truncate text-xs font-bold text-ink">{alert.title}</p><span className="shrink-0 text-[10px] text-muted">{alert.batch_id ?? "All batches"}</span></div><p className="mt-1 line-clamp-2 text-xs leading-5 text-muted">{alert.description}</p></div></div>)}{!alerts.data?.length && <div className="py-5 text-center text-sm text-muted"><CheckCircle2 className="mx-auto mb-2 text-[#18815c]" size={22} />No open alerts.</div>}</div></Panel></div>
  </div></main>;
}
