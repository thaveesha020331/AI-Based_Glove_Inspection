import { useEffect, useState } from "react";
import {
  Activity, AlertTriangle, Camera, Gauge, Hand, LoaderCircle,
  Play, ScanLine, Square, Timer, VideoOff, type LucideIcon,
} from "lucide-react";
import { apiMessage } from "../../services/api";
import {
  orientationVideoUrl, startOrientation, stopOrientation,
  subscribeOrientation, type OrientationSnapshot,
} from "../../services/liveOrientation";

const initialSnapshot: OrientationSnapshot = {
  state: "stopped", running: false, error: null, camera_index: 0,
  camera_auto_exposure: true, camera_auto_exposure_supported: null,
  model: "mobilenet_v2_classifier.torchscript.pt", classes: ["LeftHand", "RightHand"],
  raw_prediction: null, raw_confidence: null, stable_prediction: null,
  stable_confidence: null, probabilities: { LeftHand: 0, RightHand: 0 },
  fps: 0, inference_ms: null, frame_count: 0, stability_window: 7,
  minimum_confidence: 0.80, decision_state: "stopped",
  defect_model: "best.pt", defect_minimum_confidence: 0.50,
  defective: false, defect_category: null, defect_confidence: null,
  defect_detections: [], defect_inference_ms: null, defect_ready: false,
};

function percent(value: number | null | undefined): string {
  return `${Math.round((value ?? 0) * 100)}%`;
}

function Metric({ icon: Icon, label, value, detail }: { icon: LucideIcon; label: string; value: string; detail: string }) {
  return <div className="rounded-2xl border border-line bg-white p-4 shadow-soft">
    <div className="flex items-center justify-between"><p className="text-xs font-semibold text-muted">{label}</p><Icon size={17} className="text-brand" /></div>
    <p className="heading mt-3 text-2xl font-extrabold text-ink">{value}</p><p className="mt-1 text-[10px] text-muted">{detail}</p>
  </div>;
}

export function GloveOrientationPage() {
  const [snapshot, setSnapshot] = useState(initialSnapshot);
  const [streamConnected, setStreamConnected] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [runId, setRunId] = useState(0);

  useEffect(() => subscribeOrientation((next) => {
    setSnapshot(next);
    setStreamConnected(true);
  }, () => setStreamConnected(false)), []);

  async function start() {
    setBusy(true); setMessage(null);
    try { setSnapshot(await startOrientation()); setRunId((value) => value + 1); }
    catch (error) { setMessage(apiMessage(error)); }
    finally { setBusy(false); }
  }

  async function stop() {
    setBusy(true); setMessage(null);
    try { setSnapshot(await stopOrientation()); }
    catch (error) { setMessage(apiMessage(error)); }
    finally { setBusy(false); }
  }

  const prediction = snapshot.stable_prediction;
  const isAnalyzing = snapshot.decision_state === "analyzing" || snapshot.state === "starting";
  const resultLabel = prediction
    ? prediction === "LeftHand" ? "Left hand" : "Right hand"
    : isAnalyzing ? "Analyzing..." : snapshot.state === "running" ? "No glove / uncertain" : "-";
  const status = snapshot.state === "running" ? "Model running" : snapshot.state === "starting" ? "Starting camera" : snapshot.state === "error" ? "Model error" : "Model stopped";
  const statusStyle = snapshot.state === "running" ? "bg-emerald-50 text-emerald-700" : snapshot.state === "error" ? "bg-red-50 text-red-700" : snapshot.state === "starting" ? "bg-amber-50 text-amber-700" : "bg-slate-100 text-slate-600";

  return <main className="page-grid min-h-[calc(100vh-76px)] p-4 sm:p-5 lg:p-8"><div className="mx-auto max-w-[1500px]">
    <div className="mb-7 flex flex-col justify-between gap-4 md:flex-row md:items-end">
      <div><p className="text-xs font-bold uppercase tracking-[.16em] text-brand">Component 4 - Live vision</p><h2 className="heading mt-2 text-2xl font-extrabold tracking-tight text-ink sm:text-[30px]">Glove Hand Orientation</h2><p className="mt-1 text-sm text-muted">Classify a visible glove as left or right hand in real time.</p></div>
      <div className="flex flex-wrap items-center gap-3"><span className={`inline-flex items-center gap-2 rounded-full px-3 py-2 text-xs font-extrabold ${statusStyle}`}>{snapshot.state === "starting" ? <LoaderCircle className="animate-spin" size={15} /> : <Activity size={15} />}{status}</span>{snapshot.running ? <button disabled={busy} onClick={stop} className="focus-ring inline-flex items-center gap-2 rounded-xl bg-red-600 px-4 py-2.5 text-xs font-extrabold text-white hover:bg-red-700 disabled:opacity-50"><Square size={14} fill="currentColor" />Stop model</button> : <button disabled={busy} onClick={start} className="focus-ring inline-flex items-center gap-2 rounded-xl bg-brand px-4 py-2.5 text-xs font-extrabold text-white hover:opacity-90 disabled:opacity-50"><Play size={15} fill="currentColor" />Start model</button>}</div>
    </div>

    {(message || snapshot.error) && <div className="mb-5 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-xs text-red-700"><AlertTriangle size={17} className="mt-0.5 shrink-0" /><div><p className="font-bold">Live orientation could not run</p><p className="mt-1">{message || snapshot.error}</p></div></div>}

    <div className="grid gap-5 xl:grid-cols-[1.35fr_.65fr]">
      <section className="overflow-hidden rounded-2xl border border-line bg-[#101925] shadow-soft">
        <div className="flex items-center justify-between border-b border-white/10 px-5 py-4 text-white"><div><h3 className="heading text-sm font-bold">Orientation camera feed</h3><p className="mt-1 text-[11px] text-slate-400">Camera {snapshot.camera_index} - auto exposure {snapshot.camera_auto_exposure ? snapshot.camera_auto_exposure_supported === false ? "unsupported" : "on" : "off"} - 192 x 192 inference</p></div><span className={`h-2.5 w-2.5 rounded-full ${snapshot.state === "running" ? "animate-pulse bg-emerald-400" : "bg-slate-600"}`} /></div>
        <div className="relative grid min-h-[390px] place-items-center bg-[#0a111b]">{snapshot.running ? <img key={runId} src={orientationVideoUrl(runId)} className="h-full max-h-[620px] w-full object-contain" alt="Live glove orientation camera" /> : <div className="px-6 text-center text-slate-400"><VideoOff className="mx-auto" size={44} strokeWidth={1.4} /><p className="mt-4 text-sm font-bold text-slate-200">Camera is off</p><p className="mt-1 max-w-sm text-xs leading-5">Select Start model to load the model and open the backend webcam.</p></div>}<div className="absolute bottom-4 left-4 rounded-lg bg-black/65 px-3 py-2 text-[10px] font-semibold text-slate-200 backdrop-blur">{streamConnected ? "STATUS STREAM CONNECTED" : "STATUS STREAM RECONNECTING"}</div></div>
      </section>

      <section className="surface-glow rounded-2xl border border-line p-5 shadow-soft">
        <div className="flex items-center justify-between"><div><h3 className="heading text-sm font-bold text-ink">Stable result</h3><p className="mt-1 text-xs text-muted">Smoothed across {snapshot.stability_window} frames</p></div><ScanLine size={19} className="text-brand" /></div>
        <div className={`mt-5 rounded-2xl border p-6 text-center ${prediction ? "border-emerald-200 bg-emerald-50" : "border-amber-200 bg-amber-50"}`}><Hand className={`mx-auto ${prediction ? "text-emerald-600" : "text-amber-400"}`} size={44} /><p className="heading mt-3 text-3xl font-extrabold text-ink">{resultLabel}</p><p className={`mt-2 text-sm font-bold ${prediction ? "text-emerald-700" : "text-amber-700"}`}>{prediction ? `${percent(snapshot.stable_confidence)} confidence` : isAnalyzing ? "Checking consecutive frames" : `No reliable result - needs at least ${percent(snapshot.minimum_confidence)}`}</p></div>
        <div className="mt-5 space-y-4">{snapshot.classes.map((name) => { const value = snapshot.probabilities[name] ?? 0; return <div key={name}><div className="mb-1.5 flex justify-between text-xs"><span className="font-bold text-ink">{name === "LeftHand" ? "Left hand" : "Right hand"}</span><span className="font-semibold text-muted">{percent(value)}</span></div><div className="h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-brand transition-all duration-300" style={{ width: percent(value) }} /></div></div>; })}</div>
        <div className="mt-5 border-t border-line pt-4 text-[11px] text-muted"><div className="flex justify-between gap-4"><span>Raw model vote (diagnostic)</span><span className="font-bold text-ink">{snapshot.raw_prediction ?? "-"} {snapshot.raw_confidence === null ? "" : percent(snapshot.raw_confidence)}</span></div><div className="mt-2 flex justify-between gap-4"><span>Model file</span><span className="max-w-[210px] truncate font-mono text-[10px] text-ink" title={snapshot.model}>{snapshot.model}</span></div></div>
      </section>
    </div>

    <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><Metric label="Stable confidence" value={percent(snapshot.stable_confidence)} detail="EMA + majority vote" icon={Gauge} /><Metric label="Camera throughput" value={`${snapshot.fps.toFixed(1)} FPS`} detail={`${snapshot.frame_count.toLocaleString()} frames processed`} icon={Camera} /><Metric label="Inference latency" value={snapshot.inference_ms === null ? "-" : `${snapshot.inference_ms.toFixed(1)} ms`} detail="Orientation model CPU inference" icon={Timer} /><Metric label="Decision threshold" value={percent(snapshot.minimum_confidence)} detail={`${snapshot.stability_window}-frame stability window`} icon={ScanLine} /></div>
  </div></main>;
}
