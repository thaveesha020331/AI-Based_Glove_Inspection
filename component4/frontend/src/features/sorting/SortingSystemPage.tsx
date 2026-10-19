import { useEffect, useMemo, useState } from "react";
import {
  Activity, AlertTriangle, CheckCircle2, Clock3, Gauge, Radio,
  Route, Send, Wifi, WifiOff, Wind, type LucideIcon,
} from "lucide-react";
import { sortingLivePath, subscribeToSortingData } from "../../services/firebase";

type ConnectionState = "connecting" | "live" | "offline" | "error";
type AnyRecord = Record<string, unknown>;
type SensorName = "s1" | "s2" | "v1" | "v2";

type SortingSnapshot = {
  eventId: string;
  decision: string;
  state: string;
  status: string;
  destination: string;
  speedMps: number | null;
  travelTimeMs: number | null;
  triggerWaitMs: number | null;
  timestamp: number | null;
  online: boolean | null;
  wifiRssi: number | null;
  uptimeMs: number | null;
  sensors: Record<SensorName, boolean>;
  relays: { relay1: boolean; relay2: boolean };
};

const emptySnapshot: SortingSnapshot = {
  eventId: "—", decision: "NONE", state: "IDLE", status: "WAITING_FOR_DATA",
  destination: "UNKNOWN", speedMps: null, travelTimeMs: null,
  triggerWaitMs: null, timestamp: null, online: null, wifiRssi: null, uptimeMs: null,
  sensors: { s1: false, s2: false, v1: false, v2: false },
  relays: { relay1: false, relay2: false },
};

function record(value: unknown): AnyRecord {
  return value && typeof value === "object" ? value as AnyRecord : {};
}

function first(source: AnyRecord, keys: string[]): unknown {
  for (const key of keys) {
    if (source[key] !== undefined && source[key] !== null) return source[key];
  }
  return undefined;
}

function asText(value: unknown, fallback: string): string {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function asNumber(value: unknown): number | null {
  if (value === undefined || value === null || value === "") return null;
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function isActive(value: unknown): boolean {
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value === 1;
  return ["1", "true", "active", "on", "triggered", "low"].includes(String(value).toLowerCase());
}

function asBoolean(value: unknown): boolean | null {
  if (value === undefined || value === null) return null;
  return isActive(value);
}

function formatUptime(value: number | null): string {
  if (value === null) return "—";
  const seconds = Math.floor(value / 1000);
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m ${seconds % 60}s`;
}

function normalize(value: unknown): SortingSnapshot {
  const root = record(value);
  const data = record(root.current ?? root.latest ?? root);
  const sensors = record(data.sensors ?? data.sensor_values);
  const speedSensors = record(data.speed_sensors);
  const verificationSensors = record(data.verification_sensors);
  const relays = record(data.relays ?? data.outputs);
  const rawTimestamp = first(data, ["updated_at", "timestamp", "time", "last_update"]);
  let timestamp = typeof rawTimestamp === "string" ? Date.parse(rawTimestamp) : asNumber(rawTimestamp);
  if (timestamp !== null && timestamp < 10_000_000_000) timestamp *= 1000;

  return {
    eventId: asText(first(data, ["event_id", "eventId", "glove_id"]), "—"),
    decision: asText(first(data, ["decision", "classification"]), "NONE").toUpperCase(),
    state: asText(first(data, ["state", "system_state"]), "IDLE").toUpperCase(),
    status: asText(first(data, ["sorting_status", "status"]), "WAITING_FOR_DATA").toUpperCase(),
    destination: asText(first(data, ["actual_destination", "destination"]), "UNKNOWN").toUpperCase(),
    speedMps: asNumber(first(data, ["speed_mps", "conveyor_speed", "speed"])),
    travelTimeMs: asNumber(first(data, ["travel_time_ms", "travel_time"])),
    triggerWaitMs: asNumber(first(data, ["trigger_wait_ms", "trigger_delay_ms", "trigger_wait"])),
    timestamp: timestamp !== null && Number.isFinite(timestamp) ? timestamp : null,
    online: asBoolean(data.online),
    wifiRssi: asNumber(data.wifi_rssi),
    uptimeMs: asNumber(data.uptime_ms),
    sensors: {
      s1: isActive(first(sensors, ["s1", "S1"]) ?? first(speedSensors, ["s1", "S1"]) ?? first(data, ["s1", "sensor_s1"])),
      s2: isActive(first(sensors, ["s2", "S2"]) ?? first(speedSensors, ["s2", "S2"]) ?? first(data, ["s2", "sensor_s2"])),
      v1: isActive(first(sensors, ["v1", "V1"]) ?? first(verificationSensors, ["v1", "V1"]) ?? first(data, ["v1", "sensor_v1"])),
      v2: isActive(first(sensors, ["v2", "V2"]) ?? first(verificationSensors, ["v2", "V2"]) ?? first(data, ["v2", "sensor_v2"])),
    },
    relays: {
      relay1: isActive(first(relays, ["relay1", "relay_1"]) ?? first(data, ["relay1", "relay_1"])),
      relay2: isActive(first(relays, ["relay2", "relay_2"]) ?? first(data, ["relay2", "relay_2"])),
    },
  };
}

function Badge({ value }: { value: string }) {
  const positive = ["CORRECT", "COMPLETE", "ACCEPT_INFERRED"].includes(value);
  const negative = value.includes("ERROR") || value.includes("TIMEOUT");
  const style = positive ? "bg-emerald-50 text-emerald-700" : negative
    ? "bg-red-50 text-red-600" : "bg-sky-50 text-brand";
  return <span className={`inline-flex rounded-full px-2.5 py-1 text-[10px] font-extrabold tracking-wide ${style}`}>{value.split("_").join(" ")}</span>;
}

function Metric({ label, value, unit, icon: Icon }: { label: string; value: string; unit?: string; icon: LucideIcon }) {
  return <div className="surface-glow rounded-2xl border border-line p-4 shadow-soft"><div className="flex items-center justify-between"><p className="text-xs font-semibold text-muted">{label}</p><Icon size={17} className="text-brand" /></div><p className="heading mt-3 text-2xl font-extrabold text-ink">{value}<span className="ml-1 text-xs font-semibold text-muted">{unit}</span></p></div>;
}

function Sensor({ name, description, active }: { name: string; description: string; active: boolean }) {
  return <div className={`rounded-xl border p-4 transition-colors ${active ? "border-emerald-300 bg-emerald-50" : "border-line bg-slate-50"}`}><div className="flex items-center justify-between"><div><p className="text-sm font-extrabold text-ink">{name}</p><p className="mt-1 text-[11px] text-muted">{description}</p></div><span className={`h-3 w-3 rounded-full ${active ? "animate-pulse bg-emerald-500 shadow-[0_0_0_5px_rgba(16,185,129,.12)]" : "bg-slate-300"}`} /></div><p className={`mt-3 text-[10px] font-extrabold uppercase tracking-wider ${active ? "text-emerald-700" : "text-slate-400"}`}>{active ? "Triggered" : "Clear"}</p></div>;
}

export function SortingSystemPage() {
  const [connection, setConnection] = useState<ConnectionState>("connecting");
  const [snapshot, setSnapshot] = useState<SortingSnapshot>(emptySnapshot);
  const [error, setError] = useState<string | null>(null);
  const [receivedAt, setReceivedAt] = useState<number | null>(null);
  const [events, setEvents] = useState<SortingSnapshot[]>([]);

  useEffect(() => {
    let disposed = false;
    let unsubscribe: () => void = () => {};
    void subscribeToSortingData((value) => {
      if (disposed) return;
      if (value === null) {
        setSnapshot(emptySnapshot);
        setError(`No data found at /${sortingLivePath}`);
        return;
      }
      const next = normalize(value);
      setSnapshot(next);
      setReceivedAt(Date.now());
      setError(null);
      setEvents((previous) => {
        const duplicate = previous[0]?.eventId === next.eventId && previous[0]?.status === next.status;
        return next.eventId === "—" || duplicate ? previous : [next, ...previous].slice(0, 8);
      });
    }, (connected) => {
      if (!disposed) setConnection(connected ? "live" : "offline");
    }, (reason) => {
      if (disposed) return;
      setConnection("error");
      setError(reason.message);
    }).then((cleanup) => {
      if (disposed) cleanup();
      else unsubscribe = cleanup;
    }).catch((reason: unknown) => {
      if (disposed) return;
      setConnection("error");
      setError(reason instanceof Error ? reason.message : "Firebase SDK could not be loaded");
    });
    return () => { disposed = true; unsubscribe(); };
  }, []);

  const connectionMeta = useMemo(() => ({
    connecting: { label: "Connecting", icon: Radio, style: "bg-amber-50 text-amber-700" },
    live: { label: "Firebase live", icon: Wifi, style: "bg-emerald-50 text-emerald-700" },
    offline: { label: "Offline", icon: WifiOff, style: "bg-slate-100 text-slate-600" },
    error: { label: "Connection error", icon: AlertTriangle, style: "bg-red-50 text-red-600" },
  }), []);
  const connectionView = connectionMeta[connection];
  const ConnectionIcon = connectionView.icon;
  const timestamp = snapshot.timestamp ?? receivedAt;
  const relayItems = [
    { name: "Relay 1 / Nozzle 1", destination: "Defective bin", active: snapshot.relays.relay1 },
    { name: "Relay 2 / Nozzle 2", destination: "Wrong-orientation bin", active: snapshot.relays.relay2 },
  ];

  return <main className="page-grid min-h-[calc(100vh-76px)] p-4 sm:p-5 lg:p-8"><div className="mx-auto max-w-[1500px]">
    <div className="mb-7 flex flex-col justify-between gap-4 md:flex-row md:items-end"><div><p className="text-xs font-bold uppercase tracking-[.16em] text-brand">Component 3 · IoT control</p><h2 className="heading mt-2 text-2xl font-extrabold tracking-tight text-ink sm:text-[30px]">Sorting System</h2><p className="mt-1 text-sm text-muted">Live conveyor sensing, pneumatic sorting, and destination verification from Firebase.</p></div><div className="flex flex-wrap gap-2"><div className={`inline-flex items-center gap-2 rounded-full px-3 py-2 text-xs font-extrabold ${snapshot.online === false ? "bg-red-50 text-red-600" : "bg-emerald-50 text-emerald-700"}`}><Activity size={15} />{snapshot.online === null ? "Device status unknown" : snapshot.online ? "Device online" : "Device offline"}</div><div className={`inline-flex items-center gap-2 rounded-full px-3 py-2 text-xs font-extrabold ${connectionView.style}`}><ConnectionIcon size={15} />{connectionView.label}</div></div></div>

    {error && <div className="mb-5 flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs text-amber-800"><AlertTriangle size={17} className="mt-0.5 shrink-0" /><div><p className="font-bold">Live feed unavailable</p><p className="mt-1">{error}. Confirm the Realtime Database URL, path, and read rules.</p></div></div>}

    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6"><Metric label="Conveyor speed" value={snapshot.speedMps?.toFixed(2) ?? "—"} unit="m/s" icon={Gauge} /><Metric label="Travel time" value={snapshot.travelTimeMs?.toFixed(0) ?? "—"} unit="ms" icon={Route} /><Metric label="Trigger wait" value={snapshot.triggerWaitMs?.toFixed(0) ?? "—"} unit="ms" icon={Clock3} /><Metric label="Wi-Fi signal" value={snapshot.wifiRssi?.toFixed(0) ?? "—"} unit="dBm" icon={Wifi} /><Metric label="Device uptime" value={formatUptime(snapshot.uptimeMs)} icon={Activity} /><Metric label="Last live update" value={timestamp ? new Date(timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "—"} icon={Radio} /></div>

    <div className="mt-5 grid gap-5 xl:grid-cols-[1.15fr_.85fr]"><section className="surface-glow rounded-2xl border border-line p-5 shadow-soft"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-wider text-brand">Active glove event</p><h3 className="heading mt-2 text-xl font-extrabold text-ink">{snapshot.eventId}</h3></div><Badge value={snapshot.state} /></div><div className="mt-5 grid gap-3 sm:grid-cols-3"><div className="rounded-xl bg-slate-50 p-4"><p className="text-[10px] font-bold uppercase tracking-wider text-muted">Decision</p><p className="mt-2 text-sm font-extrabold text-ink">{snapshot.decision.split("_").join(" ")}</p></div><div className="rounded-xl bg-slate-50 p-4"><p className="text-[10px] font-bold uppercase tracking-wider text-muted">Destination</p><p className="mt-2 text-sm font-extrabold text-ink">{snapshot.destination.split("_").join(" ")}</p></div><div className="rounded-xl bg-slate-50 p-4"><p className="text-[10px] font-bold uppercase tracking-wider text-muted">Verification</p><div className="mt-2"><Badge value={snapshot.status} /></div></div></div><div className="mt-5 flex items-center gap-3 rounded-xl border border-line bg-white p-4"><div className={`grid h-10 w-10 place-items-center rounded-xl ${snapshot.status === "CORRECT" ? "bg-emerald-50 text-emerald-600" : "bg-sky-50 text-brand"}`}>{snapshot.status === "CORRECT" ? <CheckCircle2 size={20} /> : <Send size={20} />}</div><div><p className="text-xs font-bold text-ink">{snapshot.state === "IDLE" ? "Sorter standing by" : "Sorting cycle telemetry"}</p><p className="mt-1 text-[11px] text-muted">Realtime Database path: /{sortingLivePath}</p></div></div></section>

      <section className="surface-glow rounded-2xl border border-line p-5 shadow-soft"><h3 className="heading text-sm font-bold text-ink">Pneumatic outputs</h3><p className="mt-1 text-xs text-muted">Relay and nozzle activation states</p><div className="mt-4 space-y-3">{relayItems.map((item) => <div key={item.name} className="flex items-center justify-between rounded-xl border border-line bg-white p-4"><div className="flex items-center gap-3"><div className={`grid h-9 w-9 place-items-center rounded-lg ${item.active ? "bg-cyan-50 text-cyan-600" : "bg-slate-100 text-slate-400"}`}><Wind size={18} /></div><div><p className="text-xs font-bold text-ink">{item.name}</p><p className="mt-1 text-[10px] text-muted">{item.destination}</p></div></div><span className={`text-[10px] font-extrabold uppercase ${item.active ? "text-cyan-600" : "text-slate-400"}`}>{item.active ? "Active" : "Off"}</span></div>)}</div></section></div>

    <div className="mt-5 grid gap-5 xl:grid-cols-[.8fr_1.2fr]"><section className="surface-glow rounded-2xl border border-line p-5 shadow-soft"><h3 className="heading text-sm font-bold text-ink">Live sensor array</h3><p className="mt-1 text-xs text-muted">Green indicates the latest triggered state.</p><div className="mt-4 grid grid-cols-2 gap-3"><Sensor name="S1" description="Entry timing" active={snapshot.sensors.s1} /><Sensor name="S2" description="Speed timing" active={snapshot.sensors.s2} /><Sensor name="V1" description="Defective bin" active={snapshot.sensors.v1} /><Sensor name="V2" description="Orientation bin" active={snapshot.sensors.v2} /></div></section>
      <section className="surface-glow rounded-2xl border border-line p-5 shadow-soft"><h3 className="heading text-sm font-bold text-ink">Live event feed</h3><p className="mt-1 text-xs text-muted">Recent changes observed during this browser session</p><div className="mt-4 overflow-hidden">{events.length ? <div className="divide-y divide-slate-100">{events.map((event, index) => <div key={`${event.eventId}-${event.status}-${index}`} className="grid grid-cols-[1fr_auto] gap-3 py-3"><div><p className="text-xs font-extrabold text-ink">{event.eventId}</p><p className="mt-1 text-[11px] text-muted">{event.decision.split("_").join(" ")} → {event.destination.split("_").join(" ")}</p></div><Badge value={event.status} /></div>)}</div> : <div className="rounded-xl border border-dashed border-line p-8 text-center"><Radio className="mx-auto text-slate-300" size={28} /><p className="mt-2 text-sm font-bold text-ink">Waiting for the first event</p><p className="mt-1 text-xs text-muted">Updates will appear automatically.</p></div>}</div></section></div>
  </div></main>;
}
