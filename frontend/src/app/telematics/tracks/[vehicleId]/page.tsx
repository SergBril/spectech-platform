"use client";

import { useEffect, useState, useMemo } from "react";
import { useRouter, useParams } from "next/navigation";
import dynamic from "next/dynamic";
import { apiFetch, getAccessToken } from "@/lib/api";
import { SpectechWebSocket } from "@/lib/websocket";
import toast from "react-hot-toast";

const MapWithNoSSR = dynamic(() => import("./trackMap"), { ssr: false });

interface GpsPoint {
  id: number;
  vehicle_id: number;
  latitude: number;
  longitude: number;
  speed?: number | null;
  engine_on?: boolean | null;
  fuel_level?: number | null;
  engine_hours?: number | null;
  recorded_at: string;
}

interface TrackStats {
  vehicle_id: number;
  points_count: number;
  total_distance_km: number;
  avg_speed_kmh: number;
  max_speed_kmh: number;
  duration_minutes: number;
  stops_count: number;
  started_at: string | null;
  ended_at: string | null;
}

type DatePreset = "today" | "yesterday" | "week" | "month" | "all";

function getSpeedColor(speed: number | null | undefined): string {
  if (speed == null) return "#6b7280";
  if (speed < 30) return "#10b981";  // зеленый - медленно
  if (speed < 70) return "#f59e0b";  // желтый - средняя
  if (speed < 90) return "#f97316";  // оранжевый - быстро
  return "#ef4444";                   // красный - опасно
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("ru-RU");
}

function formatDuration(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (hours === 0) return `${mins} мин`;
  return `${hours} ч ${mins} мин`;
}

function getDateRange(preset: DatePreset): { date_from: string | null; date_to: string | null } {
  const now = new Date();
  if (preset === "today") {
    const start = new Date(now);
    start.setHours(0, 0, 0, 0);
    return { date_from: start.toISOString(), date_to: now.toISOString() };
  }
  if (preset === "yesterday") {
    const start = new Date(now);
    start.setDate(start.getDate() - 1);
    start.setHours(0, 0, 0, 0);
    const end = new Date(start);
    end.setHours(23, 59, 59, 999);
    return { date_from: start.toISOString(), date_to: end.toISOString() };
  }
  if (preset === "week") {
    const start = new Date(now);
    start.setDate(start.getDate() - 7);
    start.setHours(0, 0, 0, 0);
    return { date_from: start.toISOString(), date_to: now.toISOString() };
  }
  if (preset === "month") {
    const start = new Date(now);
    start.setDate(start.getDate() - 30);
    start.setHours(0, 0, 0, 0);
    return { date_from: start.toISOString(), date_to: now.toISOString() };
  }
  return { date_from: null, date_to: null };
}

function exportToCSV(points: GpsPoint[], vehicleId: number) {
  const header = "id,latitude,longitude,speed,engine_on,fuel_level,engine_hours,recorded_at\n";
  const rows = points.map((p) =>
    `${p.id},${p.latitude},${p.longitude},${p.speed ?? ""},${p.engine_on ?? ""},${p.fuel_level ?? ""},${p.engine_hours ?? ""},${p.recorded_at}`
  ).join("\n");
  const blob = new Blob([header + rows], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `track_vehicle_${vehicleId}_${Date.now()}.csv`;
  link.click();
  URL.revokeObjectURL(url);
  toast.success("CSV скачан!");
}

function exportToGeoJSON(points: GpsPoint[], vehicleId: number) {
  const geojson = {
    type: "FeatureCollection",
    features: points.map((p) => ({
      type: "Feature",
      geometry: {
        type: "Point",
        coordinates: [p.longitude, p.latitude],
      },
      properties: {
        id: p.id,
        speed: p.speed,
        engine_on: p.engine_on,
        fuel_level: p.fuel_level,
        engine_hours: p.engine_hours,
        recorded_at: p.recorded_at,
      },
    })),
  };
  const blob = new Blob([JSON.stringify(geojson, null, 2)], { type: "application/geo+json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `track_vehicle_${vehicleId}_${Date.now()}.geojson`;
  link.click();
  URL.revokeObjectURL(url);
  toast.success("GeoJSON скачан!");
}

export default function TrackPage() {
  const router = useRouter();
  const params = useParams();
  const vehicleId = Number(params.vehicleId);

  const [mounted, setMounted] = useState(false);
  const [loading, setLoading] = useState(true);
  const [points, setPoints] = useState<GpsPoint[]>([]);
  const [stats, setStats] = useState<TrackStats | null>(null);
  const [preset, setPreset] = useState<DatePreset>("all");

  useEffect(() => { setMounted(true); }, []);

  useEffect(() => {
    if (!mounted || !vehicleId) return;

    async function load() {
      setLoading(true);
      try {
        const range = getDateRange(preset);
        const token = getAccessToken();
        if (!token) { router.push("/login"); return; }

        // Загружаем точки
        let trackUrl = `/telematics/gps/${vehicleId}?limit=5000`;
        if (range.date_from) trackUrl += `&date_from=${encodeURIComponent(range.date_from)}`;
        if (range.date_to) trackUrl += `&date_to=${encodeURIComponent(range.date_to)}`;

        // Загружаем статистику
        let statsUrl = `/telematics/gps/${vehicleId}/stats`;
        const statsParams: string[] = [];
        if (range.date_from) statsParams.push(`date_from=${encodeURIComponent(range.date_from)}`);
        if (range.date_to) statsParams.push(`date_to=${encodeURIComponent(range.date_to)}`);
        if (statsParams.length > 0) statsUrl += `?${statsParams.join("&")}`;

        const [pts, st] = await Promise.all([
          apiFetch(trackUrl).catch(() => []),
          apiFetch(statsUrl).catch(() => null),
        ]);
        setPoints(pts);
        setStats(st);
      } catch (e) {
        console.error("Failed to load track:", e);
        toast.error("Ошибка загрузки трека");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [mounted, vehicleId, preset, router]);

  const segments = useMemo(() => {
    if (points.length < 2) return [];
    const result: { positions: [number, number][]; color: string }[] = [];
    let currentSeg: { positions: [number, number][]; color: string } = {
      positions: [[points[0].latitude, points[0].longitude]],
      color: getSpeedColor(points[0].speed),
    };
    for (let i = 1; i < points.length; i++) {
      const color = getSpeedColor(points[i].speed);
      if (color === currentSeg.color) {
        currentSeg.positions.push([points[i].latitude, points[i].longitude]);
      } else {
        result.push(currentSeg);
        currentSeg = {
          positions: [currentSeg.positions[currentSeg.positions.length - 1], [points[i].latitude, points[i].longitude]],
          color,
        };
      }
    }
    result.push(currentSeg);
    return result;
  }, [points]);

  if (!mounted) return null;

  const presets: { id: DatePreset; label: string }[] = [
    { id: "today", label: "Сегодня" },
    { id: "yesterday", label: "Вчера" },
    { id: "week", label: "Неделя" },
    { id: "month", label: "Месяц" },
    { id: "all", label: "Всё время" },
  ];

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">🛣️ История трека</h1>
            <p className="text-sm text-slate-500 mt-1">Машина #{vehicleId}</p>
          </div>
          <div className="flex gap-2">
            <button onClick={() => router.push("/telematics")} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100">
              ← Назад
            </button>
          </div>
        </div>

        {/* Фильтр по датам */}
        <div className="mb-4 flex gap-2 flex-wrap">
          {presets.map((p) => (
            <button
              key={p.id}
              onClick={() => setPreset(p.id)}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
                preset === p.id
                  ? "bg-blue-600 text-white"
                  : "bg-white border border-slate-300 text-slate-600 hover:bg-slate-100"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="flex justify-center py-12">
            <p className="text-slate-500">Загрузка трека...</p>
          </div>
        ) : points.length === 0 ? (
          <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
            <p className="text-slate-500">Нет данных за выбранный период</p>
          </div>
        ) : (
          <>
            {/* Статистика */}
            {stats && (
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
                <div className="bg-white rounded-lg border border-slate-200 p-4">
                  <div className="text-xs text-slate-500">Пробег</div>
                  <div className="text-lg font-semibold text-slate-900">{stats.total_distance_km} км</div>
                </div>
                <div className="bg-white rounded-lg border border-slate-200 p-4">
                  <div className="text-xs text-slate-500">Средняя скорость</div>
                  <div className="text-lg font-semibold text-slate-900">{stats.avg_speed_kmh} км/ч</div>
                </div>
                <div className="bg-white rounded-lg border border-slate-200 p-4">
                  <div className="text-xs text-slate-500">Макс. скорость</div>
                  <div className="text-lg font-semibold text-red-600">{stats.max_speed_kmh} км/ч</div>
                </div>
                <div className="bg-white rounded-lg border border-slate-200 p-4">
                  <div className="text-xs text-slate-500">Длительность</div>
                  <div className="text-lg font-semibold text-slate-900">{formatDuration(stats.duration_minutes)}</div>
                </div>
                <div className="bg-white rounded-lg border border-slate-200 p-4">
                  <div className="text-xs text-slate-500">Точек</div>
                  <div className="text-lg font-semibold text-slate-900">{stats.points_count}</div>
                </div>
              </div>
            )}

            {/* Карта + легенда + экспорт */}
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
              <div className="lg:col-span-3 bg-white rounded-xl border border-slate-200 overflow-hidden" style={{ height: "600px" }}>
                <MapWithNoSSR segments={segments} points={points} />
              </div>
              <div className="space-y-4">
                {/* Легенда */}
                <div className="bg-white rounded-xl border border-slate-200 p-4">
                  <h3 className="font-medium text-slate-900 mb-3 text-sm">Легенда скорости</h3>
                  <div className="space-y-2 text-xs">
                    <div className="flex items-center gap-2"><div className="w-4 h-4 rounded" style={{ background: "#10b981" }}></div><span>0–30 км/ч</span></div>
                    <div className="flex items-center gap-2"><div className="w-4 h-4 rounded" style={{ background: "#f59e0b" }}></div><span>30–70 км/ч</span></div>
                    <div className="flex items-center gap-2"><div className="w-4 h-4 rounded" style={{ background: "#f97316" }}></div><span>70–90 км/ч</span></div>
                    <div className="flex items-center gap-2"><div className="w-4 h-4 rounded" style={{ background: "#ef4444" }}></div><span>{">"}90 км/ч</span></div>
                  </div>
                </div>

                {/* Экспорт */}
                <div className="bg-white rounded-xl border border-slate-200 p-4">
                  <h3 className="font-medium text-slate-900 mb-3 text-sm">Экспорт</h3>
                  <div className="space-y-2">
                    <button onClick={() => exportToCSV(points, vehicleId)} className="w-full rounded-lg bg-slate-900 px-3 py-2 text-sm text-white hover:bg-slate-800">
                      📥 Скачать CSV
                    </button>
                    <button onClick={() => exportToGeoJSON(points, vehicleId)} className="w-full rounded-lg bg-slate-900 px-3 py-2 text-sm text-white hover:bg-slate-800">
                      🗺️ Скачать GeoJSON
                    </button>
                  </div>
                </div>

                {/* Период */}
                {stats?.started_at && stats?.ended_at && (
                  <div className="bg-white rounded-xl border border-slate-200 p-4">
                    <h3 className="font-medium text-slate-900 mb-3 text-sm">Период</h3>
                    <div className="space-y-1 text-xs text-slate-600">
                      <div>🟢 Старт: {formatDate(stats.started_at)}</div>
                      <div>🔴 Конец: {formatDate(stats.ended_at)}</div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
