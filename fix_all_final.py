import os

print("Fixing frontend files...")

# --- 1. PAGE.TSX ---
page_content = '''"use client";
import { useEffect, useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { apiFetch, getAccessToken } from "@/lib/api";
import { SpectechWebSocket } from "@/lib/websocket";
import toast, { Toaster } from "react-hot-toast";

const MapWithNoSSR = dynamic(() => import("./map"), { ssr: false });

type Tab = "live" | "tracks" | "alerts" | "notifications" | "rules";

interface Vehicle { id: number; name: string; status: string; category_id?: number; year?: number; last_lat?: number; last_lon?: number; last_speed?: number; last_updated?: string; }
interface Alert { id: number; title: string; description?: string; severity: string; status: string; occurred_at: string; }
interface Notification { id: number; title: string; body: string; is_read: boolean; sent_at: string; }
interface Rule { id: number; name: string; rule_type: string; threshold?: number; severity: string; is_active: boolean; notify_email: boolean; notify_in_app: boolean; }

const severityColors: Record<string, string> = {
  info: "bg-blue-100 text-blue-800 border-blue-300",
  warning: "bg-yellow-100 text-yellow-800 border-yellow-300",
  critical: "bg-red-100 text-red-800 border-red-300",
};

export default function TelematicsPage() {
  const router = useRouter();
  const [mounted, setMounted] = useState(false);
  const [tab, setTab] = useState<Tab>("live");
  const [loading, setLoading] = useState(true);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [rules, setRules] = useState<Rule[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [selectedVehicleId, setSelectedVehicleId] = useState<number | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [gpsMessagesCount, setGpsMessagesCount] = useState(0);
  const wsRef = useRef<SpectechWebSocket | null>(null);

  useEffect(() => { setMounted(true); }, []);

  const loadAll = useCallback(async () => {
    try {
      const token = getAccessToken();
      if (!token) { router.push("/login"); return; }
      const [v, a, n, r, uc] = await Promise.all([
        apiFetch("/vehicles").catch(() => []),
        apiFetch("/telematics/alerts").catch(() => []),
        apiFetch("/telematics/notifications").catch(() => []),
        apiFetch("/telematics/rules").catch(() => []),
        apiFetch("/telematics/notifications/unread-count").catch(() => ({ count: 0 })),
      ]);
      setVehicles(v); setAlerts(a); setNotifications(n); setRules(r);
      setUnreadCount(uc?.count || 0);
    } catch (error) { console.error("Failed to load data:", error); }
    finally { setLoading(false); }
  }, [router]);

  useEffect(() => {
    if (!mounted) return;
    loadAll();
    const interval = setInterval(loadAll, 15000);
    return () => clearInterval(interval);
  }, [loadAll, mounted]);

  useEffect(() => {
    if (!mounted) return;
    const token = getAccessToken();
    if (!token) return;
    console.log("Connecting to WebSocket...");
    const ws = new SpectechWebSocket(token, {
      onConnected: () => {
        console.log("WebSocket connected");
        setWsConnected(true);
        ws.subscribe("gps");
        ws.subscribe("alerts");
      },
      onGpsPoint: (data: any) => {
        console.log("New GPS:", data);
        setGpsMessagesCount((prev) => prev + 1);
        const gpsData = data.data;
        setVehicles((prev) => {
          const exists = prev.some((v) => v.id === gpsData.vehicle_id);
          if (exists) {
            return prev.map((v) => v.id === gpsData.vehicle_id ? { ...v, last_lat: gpsData.lat, last_lon: gpsData.lon, last_speed: gpsData.speed, last_updated: gpsData.recorded_at } : v);
          }
          return [...prev, { id: gpsData.vehicle_id, name: "Machine #" + gpsData.vehicle_id, status: "online", last_lat: gpsData.lat, last_lon: gpsData.lon, last_speed: gpsData.speed, last_updated: gpsData.recorded_at }];
        });
      },
      onAlert: (data: any) => {
        console.log("New alert:", data);
        const alertData = data.data;
        setAlerts((prev) => {
          const exists = prev.some((a) => a.id === alertData.id);
          if (exists) return prev;
          return [alertData, ...prev];
        });
        const severity = alertData.severity;
        toast.error(alertData.title, {
          duration: 5000,
          style: {
            background: severity === "critical" ? "#fee2e2" : severity === "warning" ? "#fef3c7" : "#dbeafe",
            color: severity === "critical" ? "#991b1b" : severity === "warning" ? "#92400e" : "#1e40af",
            border: "2px solid " + (severity === "critical" ? "#ef4444" : severity === "warning" ? "#f59e0b" : "#3b82f6"),
          },
        });
      },
      onDisconnected: () => { console.log("WebSocket disconnected"); setWsConnected(false); },
      onError: (error: any) => console.error("WS error:", error),
    });
    ws.connect();
    wsRef.current = ws;
    return () => { ws.disconnect(); };
  }, [mounted]);

  async function acknowledgeAlert(id: number) {
    await apiFetch("/telematics/alerts/" + id + "/acknowledge", { method: "POST", body: JSON.stringify({}) });
    loadAll();
  }
  async function markNotificationRead(id: number) {
    await apiFetch("/telematics/notifications/" + id + "/read", { method: "POST" });
    loadAll();
  }
  async function seedDefaultRules() {
    await apiFetch("/telematics/rules/seed-defaults", { method: "POST" });
    loadAll();
  }
  async function toggleRule(rule: Rule) {
    if (rule.is_active) { await apiFetch("/telematics/rules/" + rule.id, { method: "DELETE" }); }
    else {
      await apiFetch("/telematics/rules", {
        method: "POST",
        body: JSON.stringify({ name: rule.name, rule_type: rule.rule_type, threshold: rule.threshold, severity: rule.severity, notify_email: rule.notify_email, notify_in_app: rule.notify_in_app }),
      });
    }
    loadAll();
  }

  const tabs = [
    { id: "live" as Tab, label: "Live" },
    { id: "tracks" as Tab, label: "Tracks" },
    { id: "alerts" as Tab, label: "Alerts" },
    { id: "notifications" as Tab, label: "Notifications" },
    { id: "rules" as Tab, label: "Rules" },
  ];
  const fmtTime = (iso: string) => new Date(iso).toLocaleString("ru-RU");

  if (!mounted) return null;

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">Telematics</h1>
            <p className="text-sm text-slate-500 mt-1">Vehicle monitoring</p>
          </div>
          <div className="flex gap-2">
            <button onClick={loadAll} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100">Refresh</button>
            <button onClick={() => router.push("/dashboard")} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100">Back</button>
          </div>
        </div>
        <div className="flex items-center gap-4 mb-4 p-3 bg-white rounded-lg border border-slate-200">
          <div className="flex items-center gap-2">
            <div className={"w-3 h-3 rounded-full " + (wsConnected ? "bg-green-500" : "bg-red-500")} />
            <span className="text-sm font-medium">{wsConnected ? "Live GPS" : "Disconnected"}</span>
          </div>
          <div className="text-sm text-slate-600">GPS: <b>{gpsMessagesCount}</b></div>
          <div className="text-sm text-slate-600">Vehicles: <b>{vehicles.filter((v) => v.last_lat && v.last_lon).length}</b></div>
        </div>
        <div className="mb-6 border-b border-slate-200">
          <nav className="flex gap-1">
            {tabs.map((t) => (
              <button key={t.id} onClick={() => setTab(t.id)} className={"px-4 py-2.5 text-sm font-medium rounded-t-lg transition " + (tab === t.id ? "bg-white text-blue-600 border-b-2 border-blue-600" : "text-slate-600 hover:bg-slate-100")}>{t.label}</button>
            ))}
          </nav>
        </div>
        {loading && vehicles.length === 0 ? (
          <div className="flex justify-center py-12"><p className="text-slate-500">Loading...</p></div>
        ) : (
          <>
            {tab === "live" && (
              <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
                <div className="lg:col-span-3 bg-white rounded-xl border border-slate-200 overflow-hidden" style={{ height: "600px" }}>
                  <MapWithNoSSR vehicles={vehicles} selectedVehicleId={selectedVehicleId} onSelectVehicle={setSelectedVehicleId} />
                </div>
                <div className="bg-white rounded-xl border border-slate-200 p-4 overflow-y-auto" style={{ maxHeight: "600px" }}>
                  <h3 className="font-medium text-slate-900 mb-3">Vehicles ({vehicles.length})</h3>
                  <div className="space-y-2">
                    {vehicles.map((v) => (
                      <button key={v.id} onClick={() => setSelectedVehicleId(v.id)} className={"w-full text-left rounded-lg border p-3 transition " + (selectedVehicleId === v.id ? "border-blue-500 bg-blue-50" : "border-slate-200 hover:border-slate-300")}>
                        <div className="font-medium text-sm">{v.name}</div>
                        <div className="text-xs text-slate-500 mt-1">{"#" + (v.category_id || "-") + " | " + v.status}</div>
                        {v.last_lat && v.last_lon && <div className="text-xs text-blue-600 mt-1">{v.last_lat.toFixed(4)}, {v.last_lon.toFixed(4)}</div>}
                        {v.last_speed !== undefined && v.last_speed > 0 && <div className="text-xs text-green-600 mt-1">{v.last_speed.toFixed(0)} km/h</div>}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}
            {tab === "alerts" && (
              <div className="bg-white rounded-xl border border-slate-200 p-6">
                <h2 className="text-lg font-medium mb-4">Active Alerts</h2>
                {alerts.length === 0 ? <p className="text-slate-400 text-center py-8">No alerts</p> : (
                  <div className="space-y-2">
                    {alerts.map((a) => (
                      <div key={a.id} className={"rounded-lg border p-4 " + (severityColors[a.severity] || severityColors.info)}>
                        <div className="flex justify-between items-start">
                          <div className="flex-1">
                            <div className="font-medium">{a.title}</div>
                            {a.description && <div className="text-sm mt-1 opacity-80">{a.description}</div>}
                            <div className="text-xs mt-2 opacity-70">{fmtTime(a.occurred_at)} | <span className="uppercase font-semibold">{a.severity}</span></div>
                          </div>
                          {a.status === "active" && <button onClick={() => acknowledgeAlert(a.id)} className="rounded border border-slate-400 bg-white px-3 py-1 text-xs text-slate-700 hover:bg-slate-50">Ack</button>}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
            {tab === "tracks" && <div className="bg-white rounded-xl border border-slate-200 p-6"><h2>Tracks</h2></div>}
            {tab === "notifications" && <div className="bg-white rounded-xl border border-slate-200 p-6"><h2>Notifications</h2></div>}
            {tab === "rules" && <div className="bg-white rounded-xl border border-slate-200 p-6"><h2>Rules</h2></div>}
          </>
        )}
      </div>
      <Toaster position="top-right" />
    </div>
  );
}
'''

with open('frontend/src/app/telematics/page.tsx', 'w', encoding='utf-8') as f:
    f.write(page_content)
print("OK: page.tsx fixed")

# --- 2. MAP.TSX ---
map_content = '''"use client";
import { useEffect } from "react";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

interface Vehicle { id: number; name: string; status: string; category_id?: number; last_lat?: number; last_lon?: number; last_speed?: number; last_updated?: string; }
interface Props { vehicles: Vehicle[]; selectedVehicleId: number | null; onSelectVehicle: (id: number) => void; }

function getIcon(status: string, speed?: number) {
  const color = speed && speed > 5 ? "#10b981" : status === "busy" ? "#f59e0b" : status === "free" ? "#3b82f6" : "#6b7280";
  return L.divIcon({
    className: "custom-marker",
    html: '<div style="background:' + color + ';width:24px;height:24px;border-radius:50%;border:3px solid white;box-shadow:0 2px 8px rgba(0,0,0,0.3);"></div>',
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  });
}

function FitBounds({ vehicles }: { vehicles: Vehicle[] }) {
  const map = useMap();
  useEffect(() => {
    const withCoords = vehicles.filter((v) => v.last_lat && v.last_lon);
    if (withCoords.length > 0) {
      const bounds = L.latLngBounds(withCoords.map((v) => [v.last_lat!, v.last_lon!] as [number, number]));
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 14 });
    }
  }, [vehicles, map]);
  return null;
}

export default function TelematicsMap({ vehicles, selectedVehicleId, onSelectVehicle }: Props) {
  const vehiclesWithCoords = vehicles.filter((v) => v.last_lat && v.last_lon);
  const defaultCenter: [number, number] = [55.7558, 37.6173];
  return (
    <MapContainer center={defaultCenter} zoom={10} style={{ height: "100%", width: "100%" }} scrollWheelZoom={true}>
      <TileLayer attribution="OpenStreetMap" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      {vehiclesWithCoords.length > 0 && <FitBounds vehicles={vehiclesWithCoords} />}
      {vehiclesWithCoords.map((v) => (
        <Marker key={v.id} position={[v.last_lat!, v.last_lon!]} icon={getIcon(v.status, v.last_speed)} eventHandlers={{ click: () => onSelectVehicle(v.id) }}>
          <Popup>
            <div className="text-sm">
              <div className="font-bold">{v.name}</div>
              <div className="text-slate-600">#{v.category_id || "-"}</div>
              <div className="mt-2">Status: <b>{v.status}</b></div>
              {v.last_speed !== undefined && <div>Speed: <b>{v.last_speed.toFixed(1)} km/h</b></div>}
            </div>
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}
'''

with open('frontend/src/app/telematics/map.tsx', 'w', encoding='utf-8') as f:
    f.write(map_content)
print("OK: map.tsx fixed")

# --- 3. SIMULATOR FIX (catch timeouts) ---
sim_path = 'backend/scripts/gps_simulator.py'
if os.path.exists(sim_path):
    with open(sim_path, 'r', encoding='utf-8') as f:
        sim_code = f.read()
    
    old_sim_call = "status = await send_gps(token, vehicle_id, lat, lon, speed)"
    new_sim_call = """try:
                    status = await send_gps(token, vehicle_id, lat, lon, speed)
                except Exception as e:
                    status = f"ERROR: {type(e).__name__}"
"""
    if old_sim_call in sim_code and "try:" not in sim_code.split(old_sim_call)[0][-50:]:
        sim_code = sim_code.replace(old_sim_call, new_sim_call)
        with open(sim_path, 'w', encoding='utf-8') as f:
            f.write(sim_code)
        print("OK: simulator fixed to catch timeouts")
    else:
        print("Simulator already has try/except or pattern not found")

# --- 4. BACKEND FIX (DB Session leak in background task) ---
tel_path = 'backend/app/api/routes/telematics.py'
if os.path.exists(tel_path):
    with open(tel_path, 'r', encoding='utf-8') as f:
        tel_code = f.read()
    
    old_bg_task = """        async def _check_alerts_bg():
            try:
                alerts = await asyncio.to_thread(
                    process_point_with_rules, db, gps_point, current_user.company_id or 0
                )"""
    
    new_bg_task = """        async def _check_alerts_bg():
            from app.core.db import SessionLocal
            db_bg = SessionLocal()
            try:
                alerts = await asyncio.to_thread(
                    process_point_with_rules, db_bg, gps_point, current_user.company_id or 0
                )"""
    
    if old_bg_task in tel_code:
        tel_code = tel_code.replace(old_bg_task, new_bg_task)
        old_finally = """            except Exception as e:
                logger.warning("Alert processing failed: %s", e)"""
        new_finally = """            except Exception as e:
                logger.warning("Alert processing failed: %s", e)
            finally:
                db_bg.close()"""
        tel_code = tel_code.replace(old_finally, new_finally)
        
        with open(tel_path, 'w', encoding='utf-8') as f:
            f.write(tel_code)
        print("OK: backend DB session leak fixed")
    else:
        print("Backend task pattern not found or already fixed")

print("\nALL FIXES APPLIED!")