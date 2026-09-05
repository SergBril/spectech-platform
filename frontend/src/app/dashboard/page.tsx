"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, getAccessToken } from "@/lib/api";

interface Vehicle {
  id: number;
  name: string;
  status: string;
}

interface Request {
  id: number;
  status: string;
  work_type: string;
}

interface FuelStats {
  transactions_count: number;
  refuels_count: number;
  drains_count: number;
  total_volume: number;
  total_cost: number;
  avg_price_per_liter: number;
  avg_consumption: number | null;
}

interface AlertItem {
  id: number;
  title: string;
  severity: string;
  status: string;
  occurred_at: string;
  vehicle_id: number;
}

export default function DashboardPage() {
  const router = useRouter();
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [requests, setRequests] = useState<Request[]>([]);
  const [fuelStats, setFuelStats] = useState<FuelStats | null>(null);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);

    const token = getAccessToken();
    if (!token) {
      router.push("/login");
      return;
    }

    async function load() {
      try {
        const [v, r, f, a] = await Promise.all([
          apiFetch<Vehicle[]>("/vehicles?limit=10"),
          apiFetch<Request[]>("/requests?limit=10"),
          apiFetch<FuelStats>("/telematics/fuel/stats").catch(() => null),
          apiFetch<AlertItem[]>("/telematics/alerts").catch(() => []),
        ]);
        setVehicles(v);
        setRequests(r);
        setFuelStats(f);
        setAlerts(a);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [router]);

  if (!mounted) {
    return null;
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-slate-500">Загрузка...</p>
      </div>
    );
  }

  const statusLabels: Record<string, string> = {
    free: "Свободна",
    on_site: "На объекте",
    repair: "В ремонте",
    idle: "В простое",
    new: "Новая",
    processing: "В обработке",
    assigned: "Назначена",
    completed: "Завершена",
  };

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-semibold text-slate-900">Дашборд</h1>
          <button
            onClick={() => {
              localStorage.clear();
              router.push("/login");
            }}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100"
          >
            Выйти
          </button>
        </div>

        {/* Карточки телеметрии */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <button onClick={() => router.push("/telematics")} className="bg-white rounded-lg border border-slate-200 p-4 hover:border-blue-400 transition text-left">
            <div className="text-2xl mb-2">🛰️</div>
            <div className="text-xs text-slate-500">Машин онлайн</div>
            <div className="text-xl font-semibold text-slate-900">{vehicles.length}</div>
          </button>
          <button onClick={() => router.push("/telematics")} className="bg-white rounded-lg border border-slate-200 p-4 hover:border-red-400 transition text-left">
            <div className="text-2xl mb-2">🚨</div>
            <div className="text-xs text-slate-500">Активных алертов</div>
            <div className="text-xl font-semibold text-red-600">{alerts.filter((a) => a.status === "active").length}</div>
          </button>
          <button onClick={() => router.push("/telematics/fuel")} className="bg-white rounded-lg border border-slate-200 p-4 hover:border-green-400 transition text-left">
            <div className="text-2xl mb-2">⛽</div>
            <div className="text-xs text-slate-500">Расход топлива</div>
            <div className="text-xl font-semibold text-slate-900">
              {fuelStats ? `${fuelStats.total_volume.toFixed(0)} л` : "—"}
            </div>
          </button>
          <button onClick={() => router.push("/telematics/fuel")} className="bg-white rounded-lg border border-slate-200 p-4 hover:border-yellow-400 transition text-left">
            <div className="text-2xl mb-2">💰</div>
            <div className="text-xs text-slate-500">Затраты на топливо</div>
            <div className="text-xl font-semibold text-slate-900">
              {fuelStats ? `${fuelStats.total_cost.toFixed(0)} ₽` : "—"}
            </div>
          </button>
        </div>

      <div className="flex gap-2">
  <button
    onClick={() => router.push("/finance")}
    className="rounded-lg bg-green-600 px-3 py-1.5 text-sm text-white hover:bg-green-700"
  >
    💰 Финансы
  </button>
  <button
    onClick={() => router.push("/telematics")}
    className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm text-white hover:bg-indigo-700"
  >
    🛰️ Телематика
  </button>
  <button
    onClick={() => router.push("/websocket-test")}
    className="rounded-lg bg-purple-600 px-3 py-1.5 text-sm text-white hover:bg-purple-700"
  >
    📡 WebSocket Test
  </button>
  <button
    onClick={() => router.push("/catalogs")}
    className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700"
  >
    📚 Справочники
  </button>
  <button
    onClick={() => {
      localStorage.clear();
      router.push("/login");
    }}
    className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100"
  >
    Выйти
  </button>
</div>


        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <h2 className="text-lg font-medium text-slate-900 mb-4">
              Техника ({vehicles.length})
            </h2>
            <div className="space-y-2">
              {vehicles.map((v) => (
                <div
                  key={v.id}
                  className="flex items-center justify-between rounded-lg border border-slate-100 px-3 py-2"
                >
                  <span className="text-sm text-slate-800">{v.name}</span>
                  <span className="text-xs text-slate-500">
                    {statusLabels[v.status] || v.status}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <h2 className="text-lg font-medium text-slate-900 mb-4">
              🚨 Последние алерты ({alerts.length})
            </h2>
            <div className="space-y-2">
              {alerts.length === 0 ? (
                <p className="text-sm text-slate-400 text-center py-4">Нет алертов 🎉</p>
              ) : (
                alerts.slice(0, 5).map((a) => (
                  <button
                    key={a.id}
                    onClick={() => router.push(`/telematics/tracks/${a.vehicle_id}`)}
                    className="w-full flex items-center justify-between rounded-lg border border-slate-100 px-3 py-2 hover:border-red-300 transition text-left"
                  >
                    <div>
                      <div className="text-sm text-slate-800">{a.title}</div>
                      <div className="text-xs text-slate-500">{new Date(a.occurred_at).toLocaleString("ru-RU")}</div>
                    </div>
                    <span className={"text-xs px-2 py-0.5 rounded-full " + (a.severity === "critical" ? "bg-red-100 text-red-700" : a.severity === "warning" ? "bg-yellow-100 text-yellow-700" : "bg-blue-100 text-blue-700")}>
                      {a.severity}
                    </span>
                  </button>
                ))
              )}
            </div>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <h2 className="text-lg font-medium text-slate-900 mb-4">
              Заявки ({requests.length})
            </h2>
            <div className="space-y-2">
              {requests.map((r) => (
                <div
                  key={r.id}
                  className="flex items-center justify-between rounded-lg border border-slate-100 px-3 py-2"
                >
                  <span className="text-sm text-slate-800">
                    #{r.id} — {r.work_type || "Без описания"}
                  </span>
                  <span className="text-xs text-slate-500">
                    {statusLabels[r.status] || r.status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
