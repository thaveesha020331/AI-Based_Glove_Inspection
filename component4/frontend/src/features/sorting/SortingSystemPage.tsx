import { useEffect, useMemo, useState } from "react";
import {
  Activity, AlertTriangle, Cable, Clock3, Cpu, Radio, RotateCcw,
  Server, Wifi, WifiOff, Zap, type LucideIcon,
} from "lucide-react";
import { subscribeSortingTelemetry } from "../../services/sortingTelemetry";

type ConnectionState = "connecting" | "live" | "offline" | "error";
type AnyRecord = Record<string, unknown>;
type SensorName = "s1" | "s2" | "v1" | "v2";
type RelayName = "relay1" | "relay2" | "relay3" | "relay4";

type SortingSnapshot = {
  status: string;
  online: boolean;
  uptimeMs: number;
  ageMs: number | null;
  timestamp: number | null;
  driverState: string;
  driverPort: string;
  driverError: string | null;
  sensors: Record<SensorName, boolean>;
  relays: Record<RelayName, boolean>;
};

const emptySnapshot: SortingSnapshot = {
  status: "waiting_for_driver",
  online: false,
  uptimeMs: 0,
  ageMs: null,
  timestamp: null,
  driverState: "not_started",
  driverPort: "COM7",
  driverError: null,
  sensors: { s1: false, s2: false, v1: false, v2: false },
  relays: { relay1: false, relay2: false, relay3: false, relay4: false },
};

function record(value: unknown): AnyRecord {
  return value && typeof value === "object" ? value as AnyRecord : {};
}

function asBoolean(value: unknown): boolean {
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value === 1;
  return ["1", "true", "active", "on", "detected"].includes(String(value).toLowerCase());
}

function asNumber(value: unknown, fallback = 0): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function normalize(value: unknown): SortingSnapshot {
  const data = record(value);
  const sensors = record(data.sensors);
  const relays = record(data.relays);
  const driver = record(data.driver);
  const receivedAt = typeof data.received_at === "string" ? Date.parse(data.received_at) : NaN;
  return {
    status: typeof data.status === "string" ? data.status : "waiting_for_driver",
    online: asBoolean(data.online),
    uptimeMs: asNumber(data.uptime_ms),
    ageMs: data.age_ms === null || data.age_ms === undefined ? null : asNumber(data.age_ms),
    timestamp: Number.isFinite(receivedAt) ? receivedAt : null,
    driverState: typeof driver.state === "string" ? driver.state : "not_started",
    driverPort: typeof driver.port === "string" ? driver.port : "COM7",
    driverError: typeof driver.last_error === "string" ? driver.last_error : null,
    sensors: {
      s1: asBoolean(sensors.speed_s1),
      s2: asBoolean(sensors.speed_s2),
      v1: asBoolean(sensors.verify_v1),
      v2: asBoolean(sensors.verify_v2),
    },
    relays: {
      relay1: asBoolean(relays.relay1),
      relay2: asBoolean(relays.relay2),
      relay3: asBoolean(relays.relay3),
      relay4: asBoolean(relays.relay4),
    },
  };
}

function formatUptime(value: number): string {
  const seconds = Math.floor(value / 1000);
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return hours ? `${hours}h ${minutes}m` : `${minutes}m ${seconds % 60}s`;
}

function signature(value: SortingSnapshot): string {
  return JSON.stringify([value.online, value.sensors, value.relays]);
}

function summary(value: SortingSnapshot): string {
  const activeSensors = Object.entries(value.sensors).filter(([, active]) => active).map(([name]) => name.toUpperCase());
  const activeRelays = Object.entries(value.relays).filter(([, active]) => active).map(([name]) => name.replace("relay", "R"));
  const sensors = activeSensors.length ? `${activeSensors.join(", ")} detected` : "All sensors clear";
  const relays = activeRelays.length ? `${activeRelays.join(", ")} on` : "all relays off";
  return `${sensors} · ${relays}`;
}

function Metric({ label, value, detail, icon: Icon }: { label: string; value: string; detail: string; icon: LucideIcon }) {
  return <div className="surface-glow rounded-2xl border border-line p-4 shadow-soft"><div className="flex items-center justify-between"><p className="text-xs font-semibold text-muted">{label}</p><Icon size={17} className="text-brand" /></div><p className="heading mt-3 text-2xl font-extrabold text-ink">{value}</p><p className="mt-1 text-[10px] text-muted">{detail}</p></div>;
}

function Sensor({ name, description, active }: { name: string; description: string; active: boolean }) {
  return <div className={`rounded-xl border p-4 transition-colors ${active ? "border-emerald-300 bg-emerald-50" : "border-line bg-slate-50"}`}><div className="flex items-center justify-between"><div><p className="text-sm font-extrabold text-ink">{name}</p><p className="mt-1 text-[11px] text-muted">{description}</p></div><span className={`h-3 w-3 rounded-full ${active ? "animate-pulse bg-emerald-500 shadow-[0_0_0_5px_rgba(16,185,129,.12)]" : "bg-slate-300"}`} /></div><p className={`mt-3 text-[10px] font-extrabold uppercase tracking-wider ${active ? "text-emerald-700" : "text-slate-400"}`}>{active ? "Detected" : "Clear"}</p></div>;
}

export function SortingSystemPage() {
  const [connection, setConnection] = useState<ConnectionState>("connecting");
  const [snapshot, setSnapshot] = useState<SortingSnapshot>(emptySnapshot);
  const [error, setError] = useState<string | null>(null);
  const [events, setEvents] = useState<SortingSnapshot[]>([]);

  useEffect(() => {
    let mounted = true;
    const unsubscribe = subscribeSortingTelemetry((payload) => {
        const next = normalize(payload);
        if (!mounted) return;
        setSnapshot(next);
        setConnection(next.online ? "live" : next.driverState === "error" ? "error" : "offline");
        setError(next.driverError);
        setEvents((previous) => previous[0] && signature(previous[0]) === signature(next)
          ? previous : [next, ...previous].slice(0, 10));
      }, () => {
        if (!mounted) return;
        setConnection("error");
        setError("The live telemetry stream is unavailable.");
      });
    return () => { mounted = false; unsubscribe(); };
  }, []);

  const connectionMeta = useMemo(() => ({
    connecting: { label: "Connecting", icon: Radio, style: "bg-amber-50 text-amber-700" },
    live: { label: "Serial driver live", icon: Wifi, style: "bg-emerald-50 text-emerald-700" },
    offline: { label: "Driver offline", icon: WifiOff, style: "bg-slate-100 text-slate-600" },
    error: { label: "API unavailable", icon: AlertTriangle, style: "bg-red-50 text-red-600" },
  }), []);
  const connectionView = connectionMeta[connection];
  const ConnectionIcon = connectionView.icon;
  const activeSensorCount = Object.values(snapshot.sensors).filter(Boolean).length;
  const activeRelayCount = Object.values(snapshot.relays).filter(Boolean).length;
  const relayItems = [
    { name: "Relay 1", description: "Defective nozzle", active: snapshot.relays.relay1 },
    { name: "Relay 2", description: "Wrong-orientation nozzle", active: snapshot.relays.relay2 },
    { name: "Relay 3", description: "Spare output", active: snapshot.relays.relay3 },
    { name: "Relay 4", description: "Spare output", active: snapshot.relays.relay4 },
  ];

  return <main className="page-grid min-h-[calc(100vh-76px)] p-4 sm:p-5 lg:p-8"><div className="mx-auto max-w-[1500px]">
    <div className="mb-7 flex flex-col justify-between gap-4 md:flex-row md:items-end"><div><p className="text-xs font-bold uppercase tracking-[.16em] text-brand">Component 3 · Serial telemetry</p><h2 className="heading mt-2 text-2xl font-extrabold tracking-tight text-ink sm:text-[30px]">Sorting System</h2><p className="mt-1 text-sm text-muted">Live microcontroller sensor and relay data delivered through the local driver and Flask API.</p></div><div className={`inline-flex items-center gap-2 self-start rounded-full px-3 py-2 text-xs font-extrabold ${connectionView.style}`}><ConnectionIcon size={15} />{connectionView.label}</div></div>

    {error && <div className="mb-5 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-xs text-red-700"><AlertTriangle size={17} className="mt-0.5 shrink-0" /><div><p className="font-bold">Telemetry connection failed</p><p className="mt-1">{error} Check that {snapshot.driverPort} is correct and not open in another program.</p></div></div>}

    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><Metric label="Controller uptime" value={formatUptime(snapshot.uptimeMs)} detail={`Automatic driver · ${snapshot.driverPort}`} icon={Cpu} /><Metric label="Active sensors" value={`${activeSensorCount} / 4`} detail="S1, S2, V1 and V2" icon={Activity} /><Metric label="Active relays" value={`${activeRelayCount} / 4`} detail="Pneumatic outputs" icon={Zap} /><Metric label="Last driver update" value={snapshot.timestamp ? new Date(snapshot.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "—"} detail={snapshot.ageMs === null ? `Driver ${snapshot.driverState}` : `${snapshot.ageMs} ms old`} icon={Clock3} /></div>

    <div className="mt-5 grid gap-5 xl:grid-cols-[1.1fr_.9fr]"><section className="surface-glow rounded-2xl border border-line p-5 shadow-soft"><div className="flex items-start justify-between gap-3"><div><h3 className="heading text-sm font-bold text-ink">Live sensor array</h3><p className="mt-1 text-xs text-muted">Green indicates a detection reported by the ESP32.</p></div><Cable size={18} className="text-brand" /></div><div className="mt-4 grid grid-cols-2 gap-3"><Sensor name="S1" description="Conveyor entry timing" active={snapshot.sensors.s1} /><Sensor name="S2" description="Conveyor speed timing" active={snapshot.sensors.s2} /><Sensor name="V1" description="Defective-bin verification" active={snapshot.sensors.v1} /><Sensor name="V2" description="Orientation-bin verification" active={snapshot.sensors.v2} /></div></section>

      <section className="surface-glow rounded-2xl border border-line p-5 shadow-soft"><div className="flex items-start justify-between gap-3"><div><h3 className="heading text-sm font-bold text-ink">Relay outputs</h3><p className="mt-1 text-xs text-muted">Current pneumatic control output states</p></div><Server size={18} className="text-brand" /></div><div className="mt-4 grid gap-3 sm:grid-cols-2">{relayItems.map((item) => <div key={item.name} className={`rounded-xl border p-4 ${item.active ? "border-cyan-300 bg-cyan-50" : "border-line bg-white"}`}><div className="flex items-center justify-between"><div><p className="text-xs font-extrabold text-ink">{item.name}</p><p className="mt-1 text-[10px] text-muted">{item.description}</p></div><span className={`h-2.5 w-2.5 rounded-full ${item.active ? "animate-pulse bg-cyan-500" : "bg-slate-300"}`} /></div><p className={`mt-3 text-[10px] font-extrabold uppercase ${item.active ? "text-cyan-700" : "text-slate-400"}`}>{item.active ? "On" : "Off"}</p></div>)}</div></section></div>

    <section className="surface-glow mt-5 rounded-2xl border border-line p-5 shadow-soft"><div className="flex items-center justify-between"><div><h3 className="heading text-sm font-bold text-ink">Live data feed</h3><p className="mt-1 text-xs text-muted">Sensor and relay changes observed during this browser session</p></div><RotateCcw size={16} className="text-muted" /></div><div className="mt-4">{events.length ? <div className="divide-y divide-slate-100">{events.map((event, index) => <div key={`${event.timestamp}-${index}`} className="flex flex-col justify-between gap-2 py-3 sm:flex-row sm:items-center"><div><p className="text-xs font-bold text-ink">{summary(event)}</p><p className="mt-1 text-[10px] uppercase tracking-wider text-muted">{event.status.split("_").join(" ")}</p></div><p className="text-[11px] font-semibold text-muted">{event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : "Waiting for driver"}</p></div>)}</div> : <div className="rounded-xl border border-dashed border-line p-8 text-center"><Radio className="mx-auto text-slate-300" size={28} /><p className="mt-2 text-sm font-bold text-ink">Waiting for serial data</p><p className="mt-1 text-xs text-muted">Start the backend and driver; updates appear automatically.</p></div>}</div></section>
  </div></main>;
}
