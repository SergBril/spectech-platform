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

export default function DashboardPage() {
  const router = useRouter();
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [requests, setRequests] = useState<Request[]>([]);
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
        const [v, r] = await Promise.all([
          apiFetch<Vehicle[]>("/vehicles?limit=10"),
          apiFetch<Request[]>("/requests?limit=10"),
        ]);
        setVehicles(v);
        setRequests(r);
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
       <div className="flex gap-2">
  <button
    onClick={() => router.push("/finance")}
    className="rounded-lg bg-green-600 px-3 py-1.5 text-sm text-white hover:bg-green-700"
  >
    💰 Финансы
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