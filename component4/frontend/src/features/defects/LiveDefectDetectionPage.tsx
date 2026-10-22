import { useEffect, useState } from "react";
import {
  Activity, AlertTriangle, Camera, CircleCheck, Gauge, LoaderCircle,
  Minus, Play, Plus, ScanSearch, Square, Timer, VideoOff, type LucideIcon,
} from "lucide-react";
import { apiMessage } from "../../services/api";
import {
  defectVideoUrl, setCameraExposure, startDefectDetection, stopOrientation,
  subscribeOrientation, type OrientationSnapshot,
} from "../../services/liveOrientation";

const initialSnapshot: OrientationSnapshot = {
  state: "stopped", mode: null, running: false, error: null, camera_index: 0,
  camera_auto_exposure: false, camera_auto_exposure_supported: null,
  camera_exposure: -2, camera_gain: 0, camera_manual_exposure_supported: null,
  camera_actual_exposure: null, camera_actual_gain: null,
  model: "mobilenet_v2_classifier.torchscript.pt", classes: ["LeftHand", "RightHand"],
  raw_prediction: null, raw_confidence: null, stable_prediction: null,
  stable_confidence: null, probabilities: { LeftHand: 0, RightHand: 0 },
  fps: 0, inference_ms: null, frame_count: 0, stability_window: 7,
  minimum_confidence: 0.60, decision_state: "stopped",
  defect_model: "best.pt", defect_minimum_confidence: 0.30,
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

export function LiveDefectDetectionPage() {
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
    try { setSnapshot(await startDefectDetection()); setRunId((value) => value + 1); }
    catch (error) { setMessage(apiMessage(error)); }
    finally { setBusy(false); }
  }

  async function stop() {
    setBusy(true); setMessage(null);
    try { setSnapshot(await stopOrientation()); }
    catch (error) { setMessage(apiMessage(error)); }
    finally { setBusy(false); }
  }

  async function adjustExposure(change: number) {
    setBusy(true); setMessage(null);
    const current = snapshot.camera_actual_exposure ?? snapshot.camera_exposure;
    const next = Math.max(-7, Math.min(-2, Math.round(current + change)));
    try { setSnapshot(await setCameraExposure(next)); }
    catch (error) { setMessage(apiMessage(error)); }
    finally { setBusy(false); }
  }

  const modeRunning = snapshot.running && snapshot.mode === "defect";
  const status = modeRunning ? "Defect model running" : snapshot.running ? "Another model running" : snapshot.state === "starting" ? "Starting camera" : snapshot.state === "error" ? "Detector error" : "Detector stopped";
  const statusStyle = modeRunning ? "bg-emerald-50 text-emerald-700" : snapshot.state === "error" ? "bg-red-50 text-red-700" : snapshot.state === "starting" ? "bg-amber-50 text-amber-700" : "bg-slate-100 text-slate-600";
  const resultLabel = snapshot.defective
    ? snapshot.defect_category ?? "Defect detected"
    : snapshot.defect_ready ? "No defect detected" : modeRunning ? "Analyzing..." : "-";
  const resultStyle = snapshot.defective
    ? "border-red-200 bg-red-50 text-red-700"
    : snapshot.defect_ready ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-amber-200 bg-amber-50 text-amber-700";

  return <main className="page-grid min-h-[calc(100vh-76px)] p-4 sm:p-5 lg:p-8"><div className="mx-auto max-w-[1500px]">
    <div className="mb-7 flex flex-col justify-between gap-4 md:flex-row md:items-end">
      <div><p className="text-xs font-bold uppercase tracking-[.16em] text-brand">Component 4 - Quality vision</p><h2 className="heading mt-2 text-2xl font-extrabold tracking-tight text-ink sm:text-[30px]">Live Defect Detection</h2><p className="mt-1 text-sm text-muted">Detect generic defects, pinholes, and tears with the YOLO model in real time.</p></div>
      <div className="flex flex-wrap items-center gap-3"><div className="inline-flex items-center overflow-hidden rounded-xl border border-line bg-white shadow-sm"><button disabled={busy || (snapshot.camera_actual_exposure ?? snapshot.camera_exposure) <= -7} onClick={() => adjustExposure(-1)} className="focus-ring grid h-10 w-10 place-items-center text-muted hover:bg-slate-50 disabled:opacity-35" aria-label="Decrease hardware exposure"><Minus size={15} /></button><div className="min-w-[102px] border-x border-line px-3 text-center"><p className="text-[9px] font-bold uppercase tracking-wider text-muted">HW Exposure</p><p className="text-xs font-extrabold text-ink">{snapshot.camera_actual_exposure ?? snapshot.camera_exposure}</p></div><button disabled={busy || (snapshot.camera_actual_exposure ?? snapshot.camera_exposure) >= -2} onClick={() => adjustExposure(1)} className="focus-ring grid h-10 w-10 place-items-center text-muted hover:bg-slate-50 disabled:opacity-35" aria-label="Increase hardware exposure"><Plus size={15} /></button></div><span className={`inline-flex items-center gap-2 rounded-full px-3 py-2 text-xs font-extrabold ${statusStyle}`}>{snapshot.state === "starting" ? <LoaderCircle className="animate-spin" size={15} /> : <Activity size={15} />}{status}</span>{modeRunning ? <button disabled={busy} onClick={stop} className="focus-ring inline-flex items-center gap-2 rounded-xl bg-red-600 px-4 py-2.5 text-xs font-extrabold text-white hover:bg-red-700 disabled:opacity-50"><Square size={14} fill="currentColor" />Stop detector</button> : <button disabled={busy} onClick={start} className="focus-ring inline-flex items-center gap-2 rounded-xl bg-brand px-4 py-2.5 text-xs font-extrabold text-white hover:opacity-90 disabled:opacity-50"><Play size={15} fill="currentColor" />Start detector</button>}</div>
    </div>

    {(message || snapshot.error) && <div className="mb-5 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-xs text-red-700"><AlertTriangle size={17} className="mt-0.5 shrink-0" /><div><p className="font-bold">Live defect detection could not run</p><p className="mt-1">{message || snapshot.error}</p></div></div>}

    <div className="grid gap-5 xl:grid-cols-[1.35fr_.65fr]">
      <section className="overflow-hidden rounded-2xl border border-line bg-[#101925] shadow-soft">
        <div className="flex items-center justify-between border-b border-white/10 px-5 py-4 text-white"><div><h3 className="heading text-sm font-bold">Defect camera feed</h3><p className="mt-1 text-[11px] text-slate-400">Camera {snapshot.camera_index} - bounding boxes shown on detected defects</p></div><span className={`h-2.5 w-2.5 rounded-full ${snapshot.state === "running" ? "animate-pulse bg-emerald-400" : "bg-slate-600"}`} /></div>
        <div className="relative grid min-h-[420px] place-items-center bg-[#0a111b]">{modeRunning ? <img key={runId} src={defectVideoUrl(runId)} className="h-full max-h-[650px] w-full object-contain" alt="Live glove defect detection camera" /> : <div className="px-6 text-center text-slate-400"><VideoOff className="mx-auto" size={44} strokeWidth={1.4} /><p className="mt-4 text-sm font-bold text-slate-200">Defect camera is off</p><p className="mt-1 max-w-sm text-xs leading-5">Select Start detector to run only the defect model.</p></div>}<div className="absolute bottom-4 left-4 rounded-lg bg-black/65 px-3 py-2 text-[10px] font-semibold text-slate-200 backdrop-blur">{streamConnected ? "STATUS STREAM CONNECTED" : "STATUS STREAM RECONNECTING"}</div></div>
      </section>

      <section className="surface-glow rounded-2xl border border-line p-5 shadow-soft">
        <div className="flex items-center justify-between"><div><h3 className="heading text-sm font-bold text-ink">Inspection result</h3><p className="mt-1 text-xs text-muted">Stable across three detector samples</p></div><ScanSearch size={20} className="text-brand" /></div>
        <div className={`mt-5 rounded-2xl border p-6 text-center ${resultStyle}`}>{snapshot.defective ? <AlertTriangle className="mx-auto" size={48} /> : <CircleCheck className="mx-auto" size={48} />}<p className="heading mt-3 text-3xl font-extrabold text-ink">{resultLabel}</p><p className="mt-2 text-sm font-bold">{snapshot.defective ? `${percent(snapshot.defect_confidence)} confidence` : snapshot.defect_ready ? "Glove passed defect inspection" : `Needs at least ${percent(snapshot.defect_minimum_confidence)} confidence`}</p></div>

        <div className="mt-5"><div className="mb-2 flex items-center justify-between"><p className="text-xs font-bold text-ink">Current detections</p><span className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-bold text-muted">{snapshot.defect_detections.length}</span></div><div className="space-y-2">{snapshot.defect_detections.map((detection, index) => <div key={`${detection.category}-${index}`} className="flex items-center justify-between rounded-xl border border-line bg-white px-3 py-2.5 text-xs"><div><p className="font-bold text-ink">{detection.category}</p><p className="mt-0.5 text-[10px] text-muted">Class {detection.class_id} · {detection.area_zone ?? "image zone"}</p></div><span className="font-extrabold text-brand">{percent(detection.confidence)}</span></div>)}{snapshot.defect_ready && snapshot.defect_detections.length === 0 && <p className="rounded-xl bg-emerald-50 px-3 py-4 text-center text-xs font-semibold text-emerald-700">No active defect boxes</p>}</div></div>

        <div className="mt-5 border-t border-line pt-4 text-[11px] text-muted"><div className="flex justify-between gap-4"><span>Defect model</span><span className="font-mono text-[10px] font-bold text-ink">{snapshot.defect_model ?? "-"}</span></div><div className="mt-2 flex justify-between gap-4"><span>Orientation context</span><span className="font-bold text-ink">{snapshot.stable_prediction ?? "Uncertain"}</span></div></div>
      </section>
    </div>

    <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><Metric label="Defect confidence" value={percent(snapshot.defect_confidence)} detail={snapshot.defect_category ?? "No stable defect"} icon={Gauge} /><Metric label="Camera throughput" value={`${snapshot.fps.toFixed(1)} FPS`} detail={`${snapshot.frame_count.toLocaleString()} frames processed`} icon={Camera} /><Metric label="YOLO latency" value={snapshot.defect_inference_ms === null ? "-" : `${snapshot.defect_inference_ms.toFixed(1)} ms`} detail="CPU inference time" icon={Timer} /><Metric label="Decision threshold" value={percent(snapshot.defect_minimum_confidence)} detail="Two detections from three samples" icon={ScanSearch} /></div>
  </div></main>;
}
