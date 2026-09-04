import os
import sys

# Проверяем что мы в правильной папке
if not os.path.exists('src/app/telematics'):
    print("ERROR: Run this script from 'frontend' directory!")
    print("Current dir:", os.getcwd())
    sys.exit(1)

content = '''"use client";
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
    if (!token) { console.warn("No token"); return; }
    console.log("🔌 Connecting to WebSocket...");
    const ws = new SpectechWebSocket(token, {
      onConnected: () => {
        console.log("✅ WebSocket connected");
        setWsConnected(true);
        ws.subscribe("gps");
        ws.subscribe("alerts");
      },
      onGpsPoint: (data: any) => {
        console.log("📍 New GPS:", data);
        setGpsMessagesCount((prev) => prev + 1);
        const gpsData = data.data;
        setVehicles((prev) => {
          const exists = prev.some((v) => v.id === gpsData.vehicle_id);
          if (exists) {
            return prev.map((v) => v.id === gpsData.vehicle_id ? { ...v, last_lat: gpsData.lat, last_lon: gpsData.lon, last_speed: gpsData.speed, last_updated: gpsData.recorded_at } : v);
          }
          return [...prev, { id: gpsData.vehicle_id, name: "Машина #" + gpsData.vehicle_id, status: "online", last_lat: gpsData.lat, last_lon: gpsData.lon, last_speed: gpsData.speed, last_updated: gpsData.recorded_at }];
        });
      },
      onAlert: (data: any) => {
        console.log("🚨 New alert:", data);
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
      onDisconnected: () => { console.log("❌ WebSocket disconnected"); setWsConnected(false); },
      onError: (error: any) => console.error("WS error:", error),
    });
    ws.connect();
    wsRef.current = ws;
    return () => { console.log("🔌 Disconnecting WebSocket"); ws.disconnect(); };
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
    { id: "live" as Tab, label: "📍 Онлайн" },
    { id: "tracks" as Tab, label: "🛣️ Треки" },
    { id: "alerts" as Tab, label: "🚨 Алерты" },
    { id: "notifications" as Tab, label: "🔔 Уведомления" },
    { id: "rules" as Tab, label: "⚙️ Правила" },
  ];
  const fmtTime = (iso: string) => new Date(iso).toLocaleString("ru-RU");

  if (!mounted) return null;

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">🛰️ Телематика</h1>
            <p className="text-sm text-slate-500 mt-1">Мониторинг техники</p>
          </div>
          <div className="flex gap-2">
            <button onClick={loadAll} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100">🔄 Обновить</button>
            <button onClick={() => router.push("/dashboard")} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100">← Назад</button>
          </div>
        </div>
        <div className="flex items-center gap-4 mb-4 p-3 bg-white rounded-lg border border-slate-200">
          <div className="flex items-center gap-2">
            <div className={"w-3 h-3 rounded-full " + (wsConnected ? "bg-green-500" : "bg-red-500")} />
            <span className="text-sm font-medium">{wsConnected ? "🟢 Live GPS" : "🔴 Отключено"}</span>
          </div>
          <div className="text-sm text-slate-600">GPS: <b>{gpsMessagesCount}</b></div>
          <div className="text-sm text-slate-600">Машин: <b>{vehicles.filter((v) => v.last_lat && v.last_lon).length}</b></div>
        </div>
        <div className="mb-6 border-b border-slate-200">
          <nav className="flex gap-1">
            {tabs.map((t) => (
              <button key={t.id} onClick={() => setTab(t.id)} className={"px-4 py-2.5 text-sm font-medium rounded-t-lg transition " + (tab === t.id ? "bg-white text-blue-600 border-b-2 border-blue-600" : "text-slate-600 hover:bg-slate-100")}>{t.label}</button>
            ))}
          </nav>
        </div>
        {loading && vehicles.length === 0 ? (
          <div className="flex justify-center py-12"><p className="text-slate-500">Загрузка...</p></div>
        ) : (
          <>
            {tab === "live" && (
              <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
                <div className="lg:col-span-3 bg-white rounded-xl border border-slate-200 overflow-hidden" style={{ height: "600px" }}>
                  <MapWithNoSSR vehicles={vehicles} selectedVehicleId={selectedVehicleId} onSelectVehicle={setSelectedVehicleId} />
                </div>
                <div className="bg-white rounded-xl border border-slate-200 p-4 overflow-y-auto" style={{ maxHeight: "600px" }}>
                  <h3 className="font-medium text-slate-900 mb-3">Техника ({vehicles.length})</h3>
                  <div className="space-y-2">
                    {vehicles.map((v) => (
                      <button key={v.id} onClick={() => setSelectedVehicleId(v.id)} className={"w-full text-left rounded-lg border p-3 transition " + (selectedVehicleId === v.id ? "border-blue-500 bg-blue-50" : "border-slate-200 hover:border-slate-300")}>
                        <div className="font-medium text-sm">{v.name}</div>
                        <div className="text-xs text-slate-500 mt-1">{"#" + (v.category_id || "—") + " • " + v.status}</div>
                        {v.last_lat && v.last_lon && <div className="text-xs text-blue-600 mt-1">📍 {v.last_lat.toFixed(4)}, {v.last_lon.toFixed(4)}</div>}
                        {v.last_speed !== undefined && v.last_speed > 0 && <div className="text-xs text-green-600 mt-1">🏎️ {v.last_speed.toFixed(0)} км/ч</div>}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}
            {tab === "alerts" && (
              <div className="bg-white rounded-xl border border-slate-200 p-6">
                <h2 className="text-lg font-medium mb-4">Активные алерты</h2>
                {alerts.length === 0 ? <p className="text-slate-400 text-center py-8">Нет алертов 🎉</p> : (
                  <div className="space-y-2">
                    {alerts.map((a) => (
                      <div key={a.id} className={"rounded-lg border p-4 " + (severityColors[a.severity] || severityColors.info)}>
                        <div className="flex justify-between items-start">
                          <div className="flex-1">
                            <div className="font-medium">{a.title}</div>
                            {a.description && <div className="text-sm mt-1 opacity-80">{a.description}</div>}
                            <div className="text-xs mt-2 opacity-70">{fmtTime(a.occurred_at)} • <span className="uppercase font-semibold">{a.severity}</span></div>
                          </div>
                          {a.status === "active" && <button onClick={() => acknowledgeAlert(a.id)} className="rounded border border-slate-400 bg-white px-3 py-1 text-xs text-slate-700 hover:bg-slate-50">Подтвердить</button>}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
            {tab === "tracks" && <div className="bg-white rounded-xl border border-slate-200 p-6"><h2 className="text-lg font-medium mb-4">История треков</h2></div>}
            {tab === "notifications" && <div className="bg-white rounded-xl border border-slate-200 p-6"><h2 className="text-lg font-medium mb-4">Уведомления</h2></div>}
            {tab === "rules" && (
              <div className="bg-white rounded-xl border border-slate-200 p-6">
                <div className="flex justify-between items-center mb-4">
                  <h2 className="text-lg font-medium">Правила алертов</h2>
                  {rules.length === 0 && <button onClick={seedDefaultRules} className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700">🎯 Создать правила</button>}
                </div>
                {rules.length === 0 ? <p className="text-slate-400 text-center py-8">Нет правил</p> : (
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
                        <th className="px-3 py-2">Название</th><th className="px-3 py-2">Тип</th><th className="px-3 py-2">Порог</th>
                        <th className="px-3 py-2">Серьёзность</th><th className="px-3 py-2">Уведомления</th><th className="px-3 py-2">Статус</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rules.map((r) => (
                        <tr key={r.id} className="border-b border-slate-100">
                          <td className="px-3 py-3">{r.name}</td>
                          <td className="px-3 py-3 font-mono text-xs">{r.rule_type}</td>
                          <td className="px-3 py-3">{r.threshold ?? "—"}</td>
                          <td className="px-3 py-3"><span className={"rounded px-2 py-0.5 text-xs " + severityColors[r.severity]}>{r.severity}</span></td>
                          <td className="px-3 py-3 text-xs">{(r.notify_in_app ? "🔔 " : "") + (r.notify_email ? "📧" : "")}</td>
                          <td className="px-3 py-3"><button onClick={() => toggleRule(r)} className={"rounded px-2 py-0.5 text-xs " + (r.is_active ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-500")}>{r.is_active ? "Активно" : "Выкл"}</button></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}
          </>
        )}
      </div>
      <Toaster position="top-right" />
    </div>
  );
}
'''

path = 'src/app/telematics/page.tsx'

# Проверяем что файл существует
if not os.path.exists(path):
    print(f"ERROR: File not found: {path}")
    sys.exit(1)

# Записываем
with open(path, 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)

# Проверяем что запись прошла
with open(path, 'r', encoding='utf-8') as f:
    final = f.read()

checks = {
    "ws.connect()": "ws.connect();" in final,
    "onAlert": "onAlert:" in final,
    'subscribe("alerts")': 'ws.subscribe("alerts");' in final,
    "single toast import": final.count('import toast, { Toaster }') == 1,
    "toast.error": "toast.error" in final,
}

print("Verification:")
all_ok = True
for k, v in checks.items():
    print(f"  {'✅' if v else '❌'} {k}")
    if not v:
        all_ok = False

if all_ok:
    print("\n✅ SUCCESS: page.tsx fully rewritten!")
else:
    print("\n❌ FAILED: Some checks failed")
    sys.exit(1)