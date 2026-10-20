import { useEffect, useMemo, useState } from "react";
import {
  Activity, AlertTriangle, Cable, Clock3, Cpu, Lightbulb, Power,
  Radio, RotateCcw, ShieldAlert, Siren, Wifi, WifiOff, Zap, type LucideIcon,
} from "lucide-react";
import { apiMessage } from "../../services/api";
import {
  configureSortingControl, resetSortingWarning, setCameraLight,
  subscribeSortingTelemetry, type SortingControl,
} from "../../services/sortingTelemetry";

type ConnectionState = "connecting" | "live" | "offline" | "error";
type AnyRecord = Record<string, unknown>;

type SortingSnapshot = {
  status: string;
  online: boolean;
  uptimeMs: number;
  ageMs: number | null;
  timestamp: number | null;
  driverState: string;
  driverPort: string;
  driverError: string | null;
  sensors: Record<"s1" | "s2" | "v1" | "v2", boolean>;
  relays: Record<"relay1" | "relay2" | "relay3" | "relay4", boolean>;
};

const emptySnapshot: SortingSnapshot = {
  status: "waiting_for_driver", online: false, uptimeMs: 0, ageMs: null,
  timestamp: null, driverState: "not_started", driverPort: "COM7", driverError: null,
  sensors: { s1: false, s2: false, v1: false, v2: false },
  relays: { relay1: false, relay2: false, relay3: false, relay4: false },
};

const emptyControl: SortingControl = {
  automatic_enabled: true, expected_orientation: "LeftHand",
  camera_light_requested: false, warning_active: false, warning_threshold: 3,
  consecutive_rejects: 0, total_decisions: 0, total_rejected: 0,
  last_action: null, last_error: null,
  relay_roles: { relay1: "damaged_glove_reject", relay2: "wrong_orientation_reject", relay3: "camera_light", relay4: "warning_light" },
};

function record(value: unknown): AnyRecord {
  return value && typeof value === "object" ? value as AnyRecord : {};
}

function bool(value: unknown): boolean {
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value === 1;
  return ["1", "true", "active", "on", "detected"].includes(String(value).toLowerCase());
}

function num(value: unknown, fallback = 0): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function normalize(payload: unknown): { snapshot: SortingSnapshot; control: SortingControl | null } {
  const data = record(payload);
  const sensors = record(data.sensors);
  const relays = record(data.relays);
  const driver = record(data.driver);
  const control = record(data.control);
  const receivedAt = typeof data.received_at === "string" ? Date.parse(data.received_at) : NaN;
  return {
    snapshot: {
      status: typeof data.status === "string" ? data.status : "waiting_for_driver",
      online: bool(data.online), uptimeMs: num(data.uptime_ms),
      ageMs: data.age_ms == null ? null : num(data.age_ms),
      timestamp: Number.isFinite(receivedAt) ? receivedAt : null,
      driverState: typeof driver.state === "string" ? driver.state : "not_started",
      driverPort: typeof driver.port === "string" ? driver.port : "COM7",
      driverError: typeof driver.last_error === "string" ? driver.last_error : null,
      sensors: { s1: bool(sensors.speed_s1), s2: bool(sensors.speed_s2), v1: bool(sensors.verify_v1), v2: bool(sensors.verify_v2) },
      relays: { relay1: bool(relays.relay1), relay2: bool(relays.relay2), relay3: bool(relays.relay3), relay4: bool(relays.relay4) },
    },
    control: Object.keys(control).length ? control as unknown as SortingControl : null,
  };
}

function formatUptime(value: number): string {
  const seconds = Math.floor(value / 1000);
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return hours ? `${hours}h ${minutes}m` : `${minutes}m ${seconds % 60}s`;
}

function Metric({ label, value, detail, icon: Icon }: { label: string; value: string; detail: string; icon: LucideIcon }) {
  return <div className="surface-glow rounded-2xl border border-line p-4 shadow-soft"><div className="flex items-center justify-between"><p className="text-xs font-semibold text-muted">{label}</p><Icon size={17} className="text-brand" /></div><p className="heading mt-3 text-2xl font-extrabold text-ink">{value}</p><p className="mt-1 text-[10px] text-muted">{detail}</p></div>;
}

function Sensor({ name, description, active }: { name: string; description: string; active: boolean }) {
  return <div className={`rounded-xl border p-4 ${active ? "border-emerald-300 bg-emerald-50" : "border-line bg-slate-50"}`}><div className="flex items-center justify-between"><div><p className="text-sm font-extrabold text-ink">{name}</p><p className="mt-1 text-[11px] text-muted">{description}</p></div><span className={`h-3 w-3 rounded-full ${active ? "animate-pulse bg-emerald-500" : "bg-slate-300"}`} /></div><p className={`mt-3 text-[10px] font-extrabold uppercase ${active ? "text-emerald-700" : "text-slate-400"}`}>{active ? "Detected" : "Clear"}</p></div>;
}

export function SortingControlPage() {
  const [connection, setConnection] = useState<ConnectionState>("connecting");
  const [snapshot, setSnapshot] = useState(emptySnapshot);
  const [control, setControl] = useState(emptyControl);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [events, setEvents] = useState<string[]>([]);

  useEffect(() => subscribeSortingTelemetry((payload) => {
    const next = normalize(payload);
    setSnapshot(next.snapshot);
    if (next.control) setControl(next.control);
    setConnection(next.snapshot.online ? "live" : next.snapshot.driverState === "error" ? "error" : "offline");
    setMessage(next.snapshot.driverError);
  }, () => { setConnection("error"); setMessage("The live telemetry stream is unavailable."); }), []);

  const connectionMeta = useMemo(() => ({
    connecting: { label: "Connecting", icon: Radio, style: "bg-amber-50 text-amber-700" },
    live: { label: "Serial driver live", icon: Wifi, style: "bg-emerald-50 text-emerald-700" },
    offline: { label: "Driver offline", icon: WifiOff, style: "bg-slate-100 text-slate-600" },
    error: { label: "Driver error", icon: AlertTriangle, style: "bg-red-50 text-red-600" },
  }), []);
  const connectionView = connectionMeta[connection];
  const ConnectionIcon = connectionView.icon;
  const cameraLightOn = snapshot.relays.relay3 || control.camera_light_requested;
  const warningOn = snapshot.relays.relay4 || control.warning_active;

  async function runAction(action: () => Promise<SortingControl>, description: string) {
    setBusy(true); setMessage(null);
    try {
      const next = await action();
      setControl(next);
      setEvents((previous) => [`${new Date().toLocaleTimeString()} - ${description}`, ...previous].slice(0, 8));
    } catch (error) { setMessage(apiMessage(error)); }
    finally { setBusy(false); }
  }

  const relayItems = [
    { key: "relay1" as const, name: "R1", description: "Damaged-glove reject", tone: "red" },
    { key: "relay2" as const, name: "R2", description: "Wrong-orientation reject", tone: "amber" },
    { key: "relay3" as const, name: "R3", description: "Camera LED light", tone: "cyan" },
    { key: "relay4" as const, name: "R4", description: "Warning light", tone: "red" },
  ];
  const lastAction = record(control.last_action);

  return <main className="page-grid min-h-[calc(100vh-76px)] p-4 sm:p-5 lg:p-8"><div className="mx-auto max-w-[1500px]">
    <div className="mb-7 flex flex-col justify-between gap-4 md:flex-row md:items-end"><div><p className="text-xs font-bold uppercase tracking-[.16em] text-brand">Component 3 - Automated relay control</p><h2 className="heading mt-2 text-2xl font-extrabold tracking-tight text-ink sm:text-[30px]">Sorting System</h2><p className="mt-1 text-sm text-muted">Automatic reject gates, camera lighting, warning logic and live ESP32 telemetry.</p></div><div className={`inline-flex items-center gap-2 self-start rounded-full px-3 py-2 text-xs font-extrabold ${connectionView.style}`}><ConnectionIcon size={15} />{connectionView.label}</div></div>

    {message && <div className="mb-5 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-xs text-red-700"><AlertTriangle size={17} className="mt-0.5 shrink-0" /><div><p className="font-bold">Sorting control message</p><p className="mt-1">{message}</p></div></div>}

    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><Metric label="Controller uptime" value={formatUptime(snapshot.uptimeMs)} detail={`${snapshot.driverPort} - ${snapshot.driverState}`} icon={Cpu} /><Metric label="Expected stream" value={control.expected_orientation === "LeftHand" ? "Left hand" : "Right hand"} detail="Opposite hand is rejected by R2" icon={Activity} /><Metric label="Consecutive rejects" value={`${control.consecutive_rejects} / ${control.warning_threshold}`} detail="R4 turns on at threshold" icon={ShieldAlert} /><Metric label="Last update" value={snapshot.timestamp ? new Date(snapshot.timestamp).toLocaleTimeString() : "-"} detail={snapshot.ageMs == null ? snapshot.status : `${snapshot.ageMs} ms old`} icon={Clock3} /></div>

    <div className="mt-5 grid gap-5 xl:grid-cols-[1fr_1fr]">
      <section className="surface-glow rounded-2xl border border-line p-5 shadow-soft"><div className="flex items-start justify-between"><div><h3 className="heading text-sm font-bold text-ink">Automatic sorting setup</h3><p className="mt-1 text-xs text-muted">Choose the hand type that should continue on the main belt.</p></div><Zap size={18} className="text-brand" /></div><div className="mt-5 grid gap-4 sm:grid-cols-2"><label className="text-xs font-bold text-ink">Expected orientation<select disabled={busy} value={control.expected_orientation} onChange={(event) => runAction(() => configureSortingControl({ expected_orientation: event.target.value as "LeftHand" | "RightHand" }), `Expected stream set to ${event.target.value}`)} className="mt-2 w-full rounded-xl border border-line bg-white px-3 py-3 text-sm"><option value="LeftHand">Left hand</option><option value="RightHand">Right hand</option></select></label><div><p className="text-xs font-bold text-ink">Automatic decisions</p><button disabled={busy} onClick={() => runAction(() => configureSortingControl({ automatic_enabled: !control.automatic_enabled }), control.automatic_enabled ? "Automatic sorting disabled" : "Automatic sorting enabled")} className={`mt-2 flex w-full items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-extrabold text-white ${control.automatic_enabled ? "bg-emerald-600" : "bg-slate-500"}`}><Power size={16} />{control.automatic_enabled ? "Enabled" : "Disabled"}</button></div></div><div className="mt-4 rounded-xl bg-slate-50 p-4 text-xs text-muted">{control.expected_orientation === "LeftHand" ? "Right-hand" : "Left-hand"} detections pulse R2. Damaged-glove decisions pulse R1. Each pulse switches off automatically in the ESP32 firmware.</div></section>

      <section className={`rounded-2xl border p-5 shadow-soft ${warningOn ? "border-red-300 bg-red-50" : "border-line bg-white"}`}><div className="flex items-start justify-between"><div><h3 className="heading text-sm font-bold text-ink">Lights and warning</h3><p className="mt-1 text-xs text-muted">Camera illumination uses R3; the reject warning uses R4.</p></div><Siren size={19} className={warningOn ? "animate-pulse text-red-600" : "text-brand"} /></div><div className="mt-5 grid gap-3 sm:grid-cols-2"><button disabled={busy || connection !== "live"} onClick={() => runAction(() => setCameraLight(!cameraLightOn), cameraLightOn ? "Camera light switched off" : "Camera light switched on")} className={`rounded-xl border p-4 text-left ${cameraLightOn ? "border-cyan-300 bg-cyan-50" : "border-line bg-slate-50"}`}><div className="flex items-center justify-between"><div><p className="text-xs font-extrabold text-ink">Camera LED</p><p className="mt-1 text-[10px] text-muted">Dashboard controlled - Relay 3</p></div><Lightbulb size={22} className={cameraLightOn ? "text-cyan-600" : "text-slate-400"} /></div><p className="mt-3 text-xs font-bold text-brand">{cameraLightOn ? "Switch off" : "Switch on"}</p></button><div className={`rounded-xl border p-4 ${warningOn ? "border-red-300 bg-white" : "border-line bg-slate-50"}`}><div className="flex items-center justify-between"><div><p className="text-xs font-extrabold text-ink">Reject warning</p><p className="mt-1 text-[10px] text-muted">Relay 4 - latched safety alert</p></div><Siren size={22} className={warningOn ? "animate-pulse text-red-600" : "text-slate-400"} /></div><button disabled={busy || !warningOn || connection !== "live"} onClick={() => runAction(resetSortingWarning, "Warning acknowledged and reset")} className="mt-3 text-xs font-bold text-red-700 disabled:text-slate-400">{warningOn ? "Acknowledge and reset" : "No active warning"}</button></div></div></section>
    </div>

    <div className="mt-5 grid gap-5 xl:grid-cols-[1.05fr_.95fr]">
      <section className="surface-glow rounded-2xl border border-line p-5 shadow-soft"><div className="flex items-start justify-between"><div><h3 className="heading text-sm font-bold text-ink">Sensors</h3><p className="mt-1 text-xs text-muted">Filtered live inputs from the ESP32-C3.</p></div><Cable size={18} className="text-brand" /></div><div className="mt-4 grid grid-cols-2 gap-3"><Sensor name="S1" description="Conveyor entry" active={snapshot.sensors.s1} /><Sensor name="S2" description="Conveyor timing" active={snapshot.sensors.s2} /><Sensor name="V1" description="Damage-bin verify" active={snapshot.sensors.v1} /><Sensor name="V2" description="Orientation-bin verify" active={snapshot.sensors.v2} /></div></section>
      <section className="surface-glow rounded-2xl border border-line p-5 shadow-soft"><div className="flex items-start justify-between"><div><h3 className="heading text-sm font-bold text-ink">Relay outputs</h3><p className="mt-1 text-xs text-muted">Confirmed states reported by the controller.</p></div><Radio size={18} className="text-brand" /></div><div className="mt-4 grid gap-3 sm:grid-cols-2">{relayItems.map((item) => { const active = snapshot.relays[item.key]; return <div key={item.key} className={`rounded-xl border p-4 ${active ? "border-cyan-300 bg-cyan-50" : "border-line bg-white"}`}><div className="flex items-center justify-between"><div><p className="text-xs font-extrabold text-ink">{item.name}</p><p className="mt-1 text-[10px] text-muted">{item.description}</p></div><span className={`h-2.5 w-2.5 rounded-full ${active ? "animate-pulse bg-cyan-500" : "bg-slate-300"}`} /></div><p className={`mt-3 text-[10px] font-extrabold uppercase ${active ? "text-cyan-700" : "text-slate-400"}`}>{active ? "On" : "Off"}</p></div>; })}</div></section>
    </div>

    <section className="surface-glow mt-5 rounded-2xl border border-line p-5 shadow-soft"><div className="flex items-center justify-between"><div><h3 className="heading text-sm font-bold text-ink">Decision activity</h3><p className="mt-1 text-xs text-muted">Automatic model decisions and controls from this browser session.</p></div><RotateCcw size={16} className="text-muted" /></div><div className="mt-4 rounded-xl bg-slate-50 p-4"><p className="text-xs font-bold text-ink">Latest system decision</p><p className="mt-1 text-xs text-muted">{lastAction.reason ? `${String(lastAction.reason).split("_").join(" ")} - ${String(lastAction.result)}` : "Waiting for the first glove decision"}</p></div>{events.length > 0 && <div className="mt-3 divide-y divide-slate-100">{events.map((event, index) => <p key={`${event}-${index}`} className="py-2 text-xs text-muted">{event}</p>)}</div>}</section>
  </div></main>;
}
