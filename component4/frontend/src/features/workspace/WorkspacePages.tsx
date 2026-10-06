import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle, CheckCircle2, Database, Download, FileText, Filter, Gauge,
  History, RefreshCw, Settings2, Upload, XCircle,
} from "lucide-react";
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis } from "recharts";

const API = "http://127.0.0.1:5000/api/v1";

type ApiState<T> = { data: T | null; loading: boolean; error: string | null };

function useApi<T>(path: string, refreshKey = 0): ApiState<T> {
  const [state, setState] = useState<ApiState<T>>({ data: null, loading: true, error: null });
  useEffect(() => {
    let active = true;
    setState({ data: null, loading: true, error: null });
    fetch(`${API}${path}`)
      .then(async (response) => {
        const body = await response.json();
        if (!response.ok) throw new Error(body.error?.message ?? "Unable to load data.");
        return body.data as T;
      })
      .then((data) => active && setState({ data, loading: false, error: null }))
      .catch((error: Error) => active && setState({ data: null, loading: false, error: error.message }));
    return () => { active = false; };
  }, [path, refreshKey]);
  return state;
}

function Shell({ eyebrow, title, description, children, action }: {
  eyebrow: string; title: string; description: string; children: React.ReactNode; action?: React.ReactNode;
}) {
  return <main className="p-5 lg:p-8"><div className="mx-auto max-w-[1500px]">
    <div className="mb-7 flex flex-col justify-between gap-4 md:flex-row md:items-end">
      <div><p className="text-xs font-bold uppercase tracking-[.16em] text-brand">{eyebrow}</p>
        <h2 className="heading mt-2 text-2xl font-extrabold tracking-tight text-ink sm:text-[28px]">{title}</h2>
        <p className="mt-1 text-sm text-muted">{description}</p></div>{action}
    </div>{children}
  </div></main>;
}

function Panel({ title, subtitle, children, action }: { title: string; subtitle?: string; children: React.ReactNode; action?: React.ReactNode }) {
  return <section className="rounded-2xl border border-line bg-white p-5 shadow-soft"><div className="mb-4 flex items-start justify-between gap-4">
    <div><h3 className="heading text-sm font-bold text-ink">{title}</h3>{subtitle && <p className="mt-1 text-xs text-muted">{subtitle}</p>}</div>{action}</div>{children}</section>;
}

function Stat({ label, value, detail, tone = "blue" }: { label: string; value: string | number; detail?: string; tone?: "blue" | "green" | "red" | "amber" }) {
  const colors = { blue: "bg-[#edf5f8] text-brand", green: "bg-[#e8f6f0] text-[#18815c]", red: "bg-[#fff0ef] text-red-500", amber: "bg-[#fff5df] text-amber-600" };
  return <div className="rounded-2xl border border-line bg-white p-4 shadow-soft"><p className="text-xs font-semibold text-muted">{label}</p><p className={`heading mt-2 text-2xl font-extrabold ${colors[tone].split(" ")[1]}`}>{value}</p>{detail && <p className="mt-1 text-[11px] text-muted">{detail}</p>}</div>;
}

function LoadingOrError({ state }: { state: ApiState<unknown> }) {
  if (state.loading) return <div className="rounded-xl border border-line bg-white p-8 text-center text-sm text-muted">Loading live data…</div>;
  if (state.error) return <div className="rounded-xl border border-[#f1d4d1] bg-[#fff8f7] p-5 text-sm text-red-600"><AlertTriangle className="mr-2 inline-block" size={16} />{state.error}<p className="mt-1 text-xs text-muted">Start the Flask API to load persistent MySQL/SQLite data.</p></div>;
  return null;
}

function Empty({ message = "No records are available yet." }) {
  return <div className="rounded-xl border border-dashed border-line p-8 text-center"><Database className="mx-auto text-slate-300" size={28} /><p className="mt-2 text-sm font-semibold text-ink">{message}</p><p className="mt-1 text-xs text-muted">Import or create records from Data Management.</p></div>;
}

function format(value: unknown) {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  return String(value);
}

function Table({ columns, rows }: { columns: string[]; rows: Record<string, unknown>[] }) {
  if (!rows.length) return <Empty />;
  return <div className="overflow-x-auto"><table className="w-full min-w-[620px] text-left text-xs"><thead><tr className="border-b border-line text-[10px] uppercase tracking-[.12em] text-slate-400">{columns.map((column) => <th key={column} className="pb-3 pr-4 font-bold">{column.split("_").join(" ")}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={String(row.id ?? row.batch_id ?? row.record_id ?? index)} className="border-b border-slate-100 last:border-0">{columns.map((column) => <td key={column} className="py-3 pr-4 text-ink">{format(row[column])}</td>)}</tr>)}</tbody></table></div>;
}

function DateControls({ granularity, setGranularity, start, setStart, end, setEnd, onRefresh }: {
  granularity: string; setGranularity: (value: string) => void; start: string; setStart: (value: string) => void; end: string; setEnd: (value: string) => void; onRefresh: () => void;
}) {
  return <div className="flex flex-wrap items-center gap-2"><select value={granularity} onChange={(event) => setGranularity(event.target.value)} className="rounded-lg border border-line bg-white px-3 py-2 text-xs font-semibold text-ink"><option value="daily">Daily</option><option value="weekly">Weekly</option><option value="monthly">Monthly</option></select><input type="date" value={start} onChange={(event) => setStart(event.target.value)} className="rounded-lg border border-line px-3 py-2 text-xs" /><span className="text-xs text-muted">to</span><input type="date" value={end} onChange={(event) => setEnd(event.target.value)} className="rounded-lg border border-line px-3 py-2 text-xs" /><button onClick={onRefresh} className="focus-ring rounded-lg border border-line p-2 text-muted hover:text-brand" aria-label="Refresh"><RefreshCw size={15} /></button></div>;
}

type Descriptive = { kpis: Record<string, number | null>; defects: { frequency_by_category: Record<string, unknown>[]; rate: number | null; denominator: string }; quality: { grade_distribution: Record<string, number>; grade_percentages: Record<string, number | null>; by_size: Record<string, unknown>[]; by_colour: Record<string, unknown>[] }; sorting: Record<string, number | null>; batch_summaries: Record<string, unknown>[]; warnings: Record<string, unknown>[] };
type PredictionMetrics = { accuracy?: number; precision?: number; recall?: number; f1?: number; sample_size?: number };
type PredictionModel = { trained?: boolean; state?: string; message?: string; model_version?: string; evaluation?: { model?: PredictionMetrics } };
type PredictionAnalytics = { model: PredictionModel; risk_distribution: Record<string, number>; history: Record<string, unknown>[] };

export function ProductionPage() {
  const [granularity, setGranularity] = useState("daily"); const [start, setStart] = useState(""); const [end, setEnd] = useState(""); const [refresh, setRefresh] = useState(0);
  const query = `?granularity=${granularity}${start ? `&start_date=${start}` : ""}${end ? `&end_date=${end}` : ""}`;
  const trends = useApi<Record<string, unknown>[]>(`/analytics/trends${query}`, refresh); const analytics = useApi<Descriptive>("/analytics/descriptive", refresh);
  const kpis = analytics.data?.kpis ?? {};
  return <Shell eyebrow="Operations" title="Production Analytics" description="Monitor production throughput, inspection coverage, and rejection performance." action={<DateControls {...{ granularity, setGranularity, start, setStart, end, setEnd }} onRefresh={() => setRefresh((v) => v + 1)} />}>
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><Stat label="Total production" value={format(kpis.production_quantity)} detail="valid production quantity" /><Stat label="Inspected quantity" value={format(kpis.inspected_quantity)} detail={`${format(kpis.inspection_coverage)}% coverage`} tone="green" /><Stat label="Accepted quantity" value={format(kpis.accepted_quantity)} tone="green" /><Stat label="Rejected quantity" value={format(kpis.rejected_quantity)} detail={`${format(kpis.rejection_rate)}% rejection rate`} tone="red" /></div>
    <div className="mt-5 grid gap-5 xl:grid-cols-[1.4fr_.8fr]"><Panel title="Production trend" subtitle="Quantities and calculated rates by selected period"><LoadingOrError state={trends} />{trends.data && <Table columns={["period", "production_quantity", "inspected_quantity", "accepted_quantity", "rejected_quantity", "rejection_rate"]} rows={trends.data} />}</Panel><Panel title="Data quality" subtitle="Warnings affecting these calculations"><LoadingOrError state={analytics} />{analytics.data?.warnings.length ? <Table columns={["code", "field", "count", "message"]} rows={analytics.data.warnings} /> : <Empty message="No data-quality warnings" />}</Panel></div>
  </Shell>;
}

export function DefectsPage() {
  const state = useApi<Descriptive>("/analytics/descriptive"); const defects = state.data?.defects;
  return <Shell eyebrow="Quality intelligence" title="Defect Analysis" description="Understand defect frequency without confusing defect events with rejected glove quantities."><LoadingOrError state={state} />{defects && <div className="grid gap-5 lg:grid-cols-[.75fr_1.25fr]"><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1"><Stat label="Defect events" value={format(defects.frequency_by_category.reduce((sum, row) => sum + Number(row.count ?? 0), 0))} detail="inspection records" tone="amber" /><Stat label="Defect event rate" value={defects.rate === null ? "Unavailable" : `${defects.rate}%`} detail={defects.denominator} tone="red" /></div><Panel title="Frequency by defect category" subtitle="Sorted by recorded event count"><Table columns={["defect_category", "count"]} rows={defects.frequency_by_category} /></Panel></div>}</Shell>;
}

export function BatchesPage() {
  const state = useApi<Descriptive>("/analytics/descriptive"); const rows = state.data?.batch_summaries ?? [];
  return <Shell eyebrow="Batch quality" title="Batch Quality" description="Compare production quality at batch level and identify runs that need review."><LoadingOrError state={state} /><Panel title="Batch summaries" subtitle="Rejection rate uses inspected quantity as its denominator"><Table columns={["batch_id", "production_quantity", "inspected_quantity", "accepted_quantity", "rejected_quantity", "rejection_rate"]} rows={rows} /></Panel></Shell>;
}

export function PredictionsPage() {
  const [refresh, setRefresh] = useState(0); const [batchId, setBatchId] = useState(""); const [message, setMessage] = useState(""); const [detail, setDetail] = useState<Record<string, unknown> | null>(null);
  const state = useApi<PredictionAnalytics>("/predictions/analytics", refresh);
  const train = async () => { setMessage("Training with the persisted batch history…"); const response = await fetch(`${API}/predictions/train`, { method: "POST" }); const body = await response.json(); setMessage(response.ok ? `Model ready: ${body.data.training_record_count} training batches.` : body.data?.message ?? body.error?.message ?? "Training is unavailable."); setRefresh((value) => value + 1); };
  const predict = async () => { if (!batchId) return; setMessage("Calculating batch risk…"); const response = await fetch(`${API}/predictions/predict`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ batch_id: batchId }) }); const body = await response.json(); setDetail(body.data?.state === "ready" ? body.data : null); setMessage(body.data?.message ?? (response.ok ? `${body.data.risk_category} risk · ${format(body.data.risk_probability)} probability.` : body.error?.message ?? "Prediction failed.")); setRefresh((value) => value + 1); };
  const model = state.data?.model; const metrics = model?.evaluation?.model; const distribution = Object.entries(state.data?.risk_distribution ?? {}).map(([name, value]) => ({ name, value }));
  const colors: Record<string, string> = { Low: "#168b87", Medium: "#e2a12e", High: "#d65b5b" };
  return <Shell eyebrow="Risk outlook" title="Predictive Analytics" description="Estimate potential quality risk from historical batch observations. Risk is a model estimate, not a guarantee." action={<div className="flex flex-wrap gap-2"><button onClick={train} className="focus-ring flex items-center gap-2 rounded-lg bg-ink px-3 py-2 text-xs font-bold text-white"><Gauge size={14} /> Train model</button><button onClick={() => setRefresh((value) => value + 1)} className="focus-ring rounded-lg border border-line bg-white p-2 text-muted" aria-label="Refresh predictions"><RefreshCw size={15} /></button></div>}>
    {message && <div className="mb-5 rounded-xl border border-[#d8e8ed] bg-[#f3f9fa] px-4 py-3 text-xs font-semibold text-brand">{message}</div>}
    <LoadingOrError state={state} />
    {state.data && <><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><Stat label="Model status" value={model?.trained ? "Ready" : model?.state === "insufficient_data" ? "Insufficient data" : "Untrained"} detail={model?.model_version ?? model?.message} tone={model?.trained ? "green" : "amber"} /><Stat label="Evaluation accuracy" value={metrics?.accuracy == null ? "Unavailable" : `${format(Number(metrics.accuracy) * 100)}%`} detail={metrics ? `${metrics.sample_size} chronological test batches` : "Train a model to evaluate"} /><Stat label="F1 score" value={metrics?.f1 == null ? "Unavailable" : format(metrics.f1)} detail="High-risk class" tone="blue" /><Stat label="Recorded predictions" value={format(state.data.history.length)} detail="persisted prediction records" /></div>
      <div className="mt-5 grid gap-5 xl:grid-cols-[.8fr_1.2fr]"><Panel title="Risk distribution" subtitle="Only persisted model predictions are shown">{distribution.length ? <div className="h-[230px]"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={distribution} dataKey="value" nameKey="name" innerRadius={58} outerRadius={88} paddingAngle={4}>{distribution.map((item) => <Cell key={item.name} fill={colors[item.name] ?? "#1d6b8f"} />)}</Pie><Tooltip /></PieChart></ResponsiveContainer></div> : <Empty message="No predictions are available" />}</Panel><Panel title="Evaluation metrics" subtitle={metrics ? "Chronological 75/25 batch split; no shuffled related records" : "Evaluation is unavailable until a reliable model is trained"}>{metrics ? <div className="h-[230px]"><ResponsiveContainer width="100%" height="100%"><BarChart data={[{ metric: "Accuracy", value: Number(metrics.accuracy ?? 0) * 100 }, { metric: "Precision", value: Number(metrics.precision ?? 0) * 100 }, { metric: "Recall", value: Number(metrics.recall ?? 0) * 100 }, { metric: "F1", value: Number(metrics.f1 ?? 0) * 100 }]} margin={{ left: 0, right: 12, top: 10, bottom: 0 }}><CartesianGrid vertical={false} stroke="#edf0f4" /><XAxis dataKey="metric" axisLine={false} tickLine={false} tick={{ fill: "#8a97a9", fontSize: 11 }} /><YAxis domain={[0, 100]} axisLine={false} tickLine={false} tick={{ fill: "#8a97a9", fontSize: 11 }} /><Tooltip formatter={(value) => [`${format(value)}%`, "score"]} /><Bar dataKey="value" fill="#1d6b8f" radius={[5, 5, 0, 0]} /></BarChart></ResponsiveContainer></div> : <Empty message="No measured evaluation metrics" />}</Panel></div>
      <div className="mt-5 grid gap-5 xl:grid-cols-[.75fr_1.25fr]"><Panel title="Batch risk lookup" subtitle="Request a prediction for an existing batch"><div className="flex gap-2"><input value={batchId} onChange={(event) => setBatchId(event.target.value)} placeholder="e.g. B-2026-001" className="min-w-0 flex-1 rounded-lg border border-line px-3 py-2 text-xs" /><button onClick={predict} disabled={!batchId} className="rounded-lg bg-brand px-4 py-2 text-xs font-bold text-white disabled:opacity-40">Predict</button></div><p className="mt-3 text-[11px] leading-5 text-muted">Low &lt; 0.33, Medium 0.33–0.65, High ≥ 0.66 predicted high-risk probability.</p>{detail && <div className="mt-4 rounded-xl border border-line bg-[#fbfcfd] p-4"><div className="flex items-center justify-between"><div><p className="text-xs font-bold text-ink">{String(detail.batch_id)}</p><p className="mt-1 text-[11px] text-muted">{String(detail.recommended_action)}</p></div><span className="rounded-full bg-[#fff5df] px-2.5 py-1 text-xs font-bold text-amber-700">{String(detail.risk_category)} · {format(detail.risk_probability)}</span></div><p className="mt-3 text-[11px] text-muted">Top indicators</p><div className="mt-2 flex flex-wrap gap-2">{(detail.contributing_features as { feature: string; importance: number }[]).map((item) => <span key={item.feature} className="rounded-md bg-white px-2 py-1 text-[10px] text-muted">{item.feature}: {format(item.importance)}</span>)}</div></div>}</Panel><Panel title="Prediction history" subtitle="Newest persisted predictions first"><Table columns={["batch_id", "predicted_risk_category", "predicted_probability", "model_version", "prediction_time", "prediction_status"]} rows={state.data.history} /></Panel></div></>}
  </Shell>;
}

export function AlertsPage() {
  const [refresh, setRefresh] = useState(0); const state = useApi<Record<string, unknown>[]>("/alerts?status=Open", refresh); const recommendations = useApi<{ warnings: Record<string, unknown>[] }>("/analytics/decision-support", refresh);
  return <Shell eyebrow="Decision support" title="Alerts & Recommendations" description="Act on open alerts and threshold warnings generated from live analytics." action={<button onClick={() => setRefresh((v) => v + 1)} className="focus-ring flex items-center gap-2 rounded-lg border border-line bg-white px-3 py-2 text-xs font-bold"><RefreshCw size={14} /> Refresh</button>}><div className="grid gap-5 xl:grid-cols-[1fr_1fr]"><Panel title="Open alerts"><LoadingOrError state={state} /><Table columns={["severity", "title", "batch_id", "triggering_metric", "observed_value", "status"]} rows={state.data ?? []} /></Panel><Panel title="Current recommendations" subtitle="Duplicate active conditions are suppressed"><LoadingOrError state={recommendations} /><Table columns={["code", "severity", "batch_id", "metric", "observed_value", "threshold", "recommendation"]} rows={recommendations.data?.warnings ?? []} /></Panel></div></Shell>;
}

export function ReportsPage() {
  const state = useApi<Record<string, unknown>[]>("/reports");
  return <Shell eyebrow="Exports" title="Reports" description="Review requested reports and their processing status." action={<button className="focus-ring flex items-center gap-2 rounded-lg bg-ink px-3 py-2 text-xs font-bold text-white"><Download size={14} /> Request report</button>}><Panel title="Report history"><LoadingOrError state={state} /><Table columns={["report_type", "status", "created_at", "file_reference"]} rows={state.data ?? []} /></Panel></Shell>;
}

export function HistoryPage() {
  const state = useApi<Record<string, unknown>[]>("/history");
  return <Shell eyebrow="Traceability" title="Historical Records" description="Browse the inspection event history stored in the persistent data source." action={<div className="flex items-center gap-2 rounded-lg border border-line bg-white px-3 py-2 text-xs text-muted"><Filter size={14} /> Filter history</div>}><Panel title="Inspection history" subtitle="Newest inspection records appear first"><LoadingOrError state={state} /><Table columns={["record_id", "batch_id", "defect_category", "defect_status", "inspection_timestamp"]} rows={state.data ?? []} /></Panel></Shell>;
}

export function DataManagementPage() {
  const [file, setFile] = useState<File | null>(null); const [kind, setKind] = useState("production"); const [message, setMessage] = useState(""); const input = useRef<HTMLInputElement>(null);
  const summary = useApi<Record<string, number>>("/data-management/summary");
  const upload = async () => { if (!file) return; setMessage("Uploading and validating…"); const form = new FormData(); form.append("file", file); form.append("record_type", kind); const response = await fetch(`${API}/data-management/import`, { method: "POST", body: form }); const body = await response.json(); setMessage(response.ok ? `Imported ${body.data.imported} ${kind} record(s).` : body.error?.message ?? "Import failed."); };
  return <Shell eyebrow="Data operations" title="Data Management" description="Import validated source records and monitor the database inventory."><div className="grid gap-5 lg:grid-cols-[1fr_.8fr]"><Panel title="Import CSV" subtitle="Records are validated transactionally before commit"><div className="rounded-xl border border-dashed border-line p-7 text-center"><Upload className="mx-auto text-brand" size={28} /><p className="mt-2 text-sm font-bold text-ink">Choose a CSV file</p><p className="mt-1 text-xs text-muted">No invalid rows are silently converted.</p><input ref={input} type="file" accept=".csv" onChange={(event) => setFile(event.target.files?.[0] ?? null)} className="mx-auto mt-4 block max-w-full text-xs" /><div className="mt-4 flex justify-center gap-2"><select value={kind} onChange={(event) => setKind(event.target.value)} className="rounded-lg border border-line px-3 py-2 text-xs"><option value="production">Production</option><option value="inspection">Inspection</option><option value="quality">Quality</option><option value="sorting">Sorting</option></select><button onClick={upload} disabled={!file} className="rounded-lg bg-brand px-4 py-2 text-xs font-bold text-white disabled:opacity-40">Import</button></div>{message && <p className="mt-4 text-xs font-semibold text-brand">{message}</p>}</div></Panel><Panel title="Database inventory" subtitle="Records available to analytics"><LoadingOrError state={summary} /><div className="grid grid-cols-2 gap-3">{Object.entries(summary.data ?? {}).map(([key, value]) => <Stat key={key} label={key.split("_").join(" ")} value={value} />)}</div></Panel></div></Shell>;
}

export function SettingsPage() {
  const state = useApi<Record<string, unknown>>("/settings");
  return <Shell eyebrow="Configuration" title="Settings" description="Review the active API configuration for this workspace."><Panel title="Runtime configuration"><LoadingOrError state={state} /><div className="divide-y divide-slate-100">{Object.entries(state.data ?? {}).map(([key, value]) => <div key={key} className="flex items-center justify-between py-3 text-xs"><span className="font-semibold text-muted">{key.split("_").join(" ")}</span><span className="font-bold text-ink">{format(value)}</span></div>)}</div></Panel></Shell>;
}
