"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, getAccessToken } from "@/lib/api";

function parseNum(v: any): number {
  if (v == null) return 0;
  const n = typeof v === 'string' ? parseFloat(v) : v;
  return isNaN(n) ? 0 : n;
}
import toast from "react-hot-toast";

interface FuelTransaction {
  id: number;
  vehicle_id: number;
  transaction_type: "refuel" | "drain";
  volume: number;
  total_cost?: number | null;
  fuel_level_before?: number | null;
  fuel_level_after?: number | null;
  occurred_at: string;
  detected_automatically: boolean;
}

interface FuelStats {
  transactions_count: number;
  refuels_count: number;
  drains_count: number;
  total_volume: number;
  total_cost: number;
  avg_price_per_liter: number;
  avg_consumption: number | null;
  last_refuel_at: string | null;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function FuelPage() {
  const router = useRouter();
  const [transactions, setTransactions] = useState<FuelTransaction[]>([]);
  const [stats, setStats] = useState<FuelStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);

  // Форма добавления
  const [formData, setFormData] = useState({
    vehicle_id: 1,
    transaction_type: "refuel" as "refuel" | "drain",
    volume: "",
    price_per_liter: "",
    fuel_level_before: "",
    fuel_level_after: "",
    odometer: "",
    occurred_at: new Date().toISOString().slice(0, 16),
  });

  useEffect(() => {
    async function load() {
      try {
        const [txs, st] = await Promise.all([
          apiFetch<FuelTransaction[]>("/telematics/fuel").catch(() => []),
          apiFetch<FuelStats>("/telematics/fuel/stats").catch(() => null),
        ]);
        setTransactions(txs);
        setStats(st);
      } catch (e) {
        console.error("Failed to load fuel data:", e);
        toast.error("Ошибка загрузки данных");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      const payload = {
        vehicle_id: formData.vehicle_id,
        transaction_type: formData.transaction_type,
        volume: parseFloat(formData.volume),
        price_per_liter: formData.price_per_liter ? parseFloat(formData.price_per_liter) : null,
        fuel_level_before: formData.fuel_level_before ? parseFloat(formData.fuel_level_before) : null,
        fuel_level_after: formData.fuel_level_after ? parseFloat(formData.fuel_level_after) : null,
        odometer: formData.odometer ? parseFloat(formData.odometer) : null,
        occurred_at: new Date(formData.occurred_at).toISOString(),
      };
      await apiFetch("/telematics/fuel", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      toast.success("Заправка добавлена!");
      setShowForm(false);
      // Перезагружаем данные
      const [txs, st] = await Promise.all([
        apiFetch<FuelTransaction[]>("/telematics/fuel"),
        apiFetch<FuelStats>("/telematics/fuel/stats"),
      ]);
      setTransactions(txs);
      setStats(st);
    } catch (e) {
      console.error("Failed to add transaction:", e);
      toast.error("Ошибка добавления");
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 p-6 flex items-center justify-center">
        <p className="text-slate-500">Загрузка...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">⛽ Топливо</h1>
            <p className="text-sm text-slate-500 mt-1">Учёт заправок и анализ расхода</p>
          </div>
          <div className="flex gap-2">
            <button onClick={() => setShowForm(!showForm)} className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700">
              {showForm ? "✖ Закрыть форму" : "➕ Добавить заправку"}
            </button>
            <button onClick={() => router.push("/telematics")} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100">
              ← Назад
            </button>
          </div>
        </div>

        {/* Статистика */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
            <div className="bg-white rounded-lg border border-slate-200 p-4">
              <div className="text-xs text-slate-500">Всего заправок</div>
              <div className="text-lg font-semibold text-slate-900">{stats.refuels_count}</div>
            </div>
            <div className="bg-white rounded-lg border border-slate-200 p-4">
              <div className="text-xs text-slate-500">Объём</div>
              <div className="text-lg font-semibold text-slate-900">{stats.total_volume.toFixed(1)} л</div>
            </div>
            <div className="bg-white rounded-lg border border-slate-200 p-4">
              <div className="text-xs text-slate-500">Стоимость</div>
              <div className="text-lg font-semibold text-slate-900">{stats.total_cost.toFixed(0)} ₽</div>
            </div>
            <div className="bg-white rounded-lg border border-slate-200 p-4">
              <div className="text-xs text-slate-500">Средняя цена</div>
              <div className="text-lg font-semibold text-slate-900">{stats.avg_price_per_liter.toFixed(2)} ₽/л</div>
            </div>
            <div className="bg-white rounded-lg border border-slate-200 p-4">
              <div className="text-xs text-slate-500">Расход</div>
              <div className="text-lg font-semibold text-slate-900">
                {stats.avg_consumption ? `${stats.avg_consumption} л/100км` : "—"}
              </div>
            </div>
          </div>
        )}

        {/* Предупреждение о сливах */}
        {stats && stats.drains_count > 0 && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <div className="flex items-center gap-2">
              <span className="text-2xl">⚠️</span>
              <div>
                <div className="font-medium text-red-900">Обнаружено {stats.drains_count} слив(ов) топлива</div>
                <div className="text-sm text-red-700 mt-1">
                  Проверьте подозрительные транзакции в таблице ниже
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Форма добавления */}
        {showForm && (
          <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
            <h2 className="text-lg font-medium mb-4">Добавить {formData.transaction_type === "refuel" ? "заправку" : "слив"}</h2>
            <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Тип</label>
                <select
                  value={formData.transaction_type}
                  onChange={(e) => setFormData({ ...formData, transaction_type: e.target.value as "refuel" | "drain" })}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                >
                  <option value="refuel">Заправка</option>
                  <option value="drain">Слив</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Объём (л) *</label>
                <input
                  type="number"
                  step="0.01"
                  required
                  value={formData.volume}
                  onChange={(e) => setFormData({ ...formData, volume: e.target.value })}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                />
              </div>
              {formData.transaction_type === "refuel" && (
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Цена за литр (₽)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={formData.price_per_liter}
                    onChange={(e) => setFormData({ ...formData, price_per_liter: e.target.value })}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  />
                </div>
              )}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Дата и время</label>
                <input
                  type="datetime-local"
                  value={formData.occurred_at}
                  onChange={(e) => setFormData({ ...formData, occurred_at: e.target.value })}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Уровень ДО (%)</label>
                <input
                  type="number"
                  step="0.1"
                  value={formData.fuel_level_before}
                  onChange={(e) => setFormData({ ...formData, fuel_level_before: e.target.value })}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Уровень ПОСЛЕ (%)</label>
                <input
                  type="number"
                  step="0.1"
                  value={formData.fuel_level_after}
                  onChange={(e) => setFormData({ ...formData, fuel_level_after: e.target.value })}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Пробег (км)</label>
                <input
                  type="number"
                  step="0.1"
                  value={formData.odometer}
                  onChange={(e) => setFormData({ ...formData, odometer: e.target.value })}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                />
              </div>
              <div className="md:col-span-2 flex gap-2">
                <button type="submit" className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700">
                  💾 Сохранить
                </button>
                <button type="button" onClick={() => setShowForm(false)} className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-600 hover:bg-slate-100">
                  Отмена
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Таблица транзакций */}
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div className="p-4 border-b border-slate-200">
            <h2 className="text-lg font-medium">История транзакций ({transactions.length})</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr className="text-left text-xs uppercase text-slate-500">
                  <th className="px-4 py-3">Дата</th>
                  <th className="px-4 py-3">Тип</th>
                  <th className="px-4 py-3">Объём</th>
                  <th className="px-4 py-3">Стоимость</th>
                  <th className="px-4 py-3">Уровень ДО → ПОСЛЕ</th>
                  <th className="px-4 py-3">Пробег</th>
                  <th className="px-4 py-3">Статус</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((tx) => (
                  <tr
                    key={tx.id}
                    onClick={() => router.push("/telematics/tracks/" + tx.vehicle_id)}
                    className="border-b border-slate-100 hover:bg-slate-50 cursor-pointer"
                  >
                    <td className="px-4 py-3 text-slate-900">{formatDate(tx.occurred_at)}</td>
                    <td className="px-4 py-3">
                      {tx.transaction_type === "refuel" ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-1 text-xs font-medium text-green-800">
                          ⛽ Заправка
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-1 text-xs font-medium text-red-800">
                          ⚠️ Слив
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 font-medium text-slate-900">{parseNum(tx.volume).toFixed(2)} л</td>
                    <td className="px-4 py-3 text-slate-700">{tx.total_cost ? `${parseNum(tx.total_cost).toFixed(2)} ₽` : "—"}</td>
                    <td className="px-4 py-3 text-slate-600">
                      {tx.fuel_level_before != null && tx.fuel_level_after != null
                        ? `${parseNum(tx.fuel_level_before).toFixed(1)}% → ${parseNum(tx.fuel_level_after).toFixed(1)}%`
                        : "—"}
                    </td>
                    <td className="px-4 py-3 text-slate-600">—</td>
                    <td className="px-4 py-3">
                      {tx.detected_automatically ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-orange-100 px-2 py-1 text-xs font-medium text-orange-800">
                          🤖 Авто
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700">
                          ✍️ Ручная
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
