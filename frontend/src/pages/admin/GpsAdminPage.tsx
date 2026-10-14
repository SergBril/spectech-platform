import React, { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import Layout from '../../components/Layout';

interface VehicleGps {
  id: number;
  name: string;
  gps_provider: string | null;
  gps_provider_config: Record<string, any> | null;
  last_point_at: string | null;
  total_points: number;
}

interface GpsStats {
  total_points: number;
  vehicles_with_data: number;
  latest_recorded_at: string | null;
  oldest_recorded_at: string | null;
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api/v1';

export default function GpsAdminPage() {
  const [vehicles, setVehicles] = useState<VehicleGps[]>([]);
  const [stats, setStats] = useState<GpsStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editProvider, setEditProvider] = useState('');
  const [editLogin, setEditLogin] = useState('');
  const [editPassword, setEditPassword] = useState('');
  const [editApiUrl, setEditApiUrl] = useState('');

  const fetchData = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const headers = token ? { Authorization: `Bearer ${token}` } : {};

      const [vehRes, statsRes] = await Promise.all([
        fetch(`${API_BASE}/gps/providers/vehicles`, { headers }),
        fetch(`${API_BASE}/gps/points/stats`, { headers }),
      ]);

      if (vehRes.ok) setVehicles(await vehRes.json());
      if (statsRes.ok) setStats(await statsRes.json());
    } catch (e) {
      toast.error('Ошибка загрузки GPS-данных');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const startEdit = (v: VehicleGps) => {
    setEditingId(v.id);
    setEditProvider(v.gps_provider || '');
    setEditLogin(v.gps_provider_config?.login || '');
    setEditPassword(v.gps_provider_config?.password || '');
    setEditApiUrl(v.gps_provider_config?.api_url || 'https://gps.mapix.su');
  };

  const saveConfig = async (vehicleId: number) => {
    try {
      const token = localStorage.getItem('access_token');
      const config = editProvider ? {
        login: editLogin,
        password: editPassword,
        api_url: editApiUrl,
      } : null;

      const res = await fetch(`${API_BASE}/gps/providers/vehicles/${vehicleId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          gps_provider: editProvider || null,
          gps_provider_config: config,
        }),
      });

      if (res.ok) {
        toast.success('Конфигурация сохранена');
        setEditingId(null);
        fetchData();
      } else {
        toast.error('Ошибка сохранения');
      }
    } catch {
      toast.error('Ошибка сети');
    }
  };

  const handleExport = async (format: 'csv' | 'excel') => {
    try {
      const token = localStorage.getItem('access_token');
      const url = `${API_BASE}/gps/points/export?format=${format}`;
      const res = await fetch(url, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Ошибка экспорта' }));
        toast.error(err.detail || 'Ошибка экспорта');
        return;
      }

      const blob = await res.blob();
      const ext = format === 'excel' ? 'xlsx' : 'csv';
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `gps_points_${new Date().toISOString().slice(0, 10)}.${ext}`;
      a.click();
      URL.revokeObjectURL(a.href);
      toast.success(`📥 ${format.toUpperCase()} экспортирован`);
    } catch {
      toast.error('Ошибка экспорта');
    }
  };

  const formatDate = (d: string | null) => {
    if (!d) return '—';
    return new Date(d).toLocaleString('ru-RU');
  };

  if (loading) {
    return (
      <Layout>
        <div className="p-8 text-center text-gray-500">Загрузка...</div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="p-6 max-w-7xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">📡 Управление GPS</h1>
          <div className="flex gap-2">
            <button
              onClick={() => handleExport('csv')}
              className="bg-green-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-green-700 flex items-center gap-2"
            >
              📥 CSV
            </button>
            <button
              onClick={() => handleExport('excel')}
              className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700 flex items-center gap-2"
            >
              📥 Excel
            </button>
          </div>
        </div>

        {/* Stats Cards */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-white rounded-lg shadow p-4">
              <div className="text-sm text-gray-500">Всего точек</div>
              <div className="text-2xl font-bold">{stats.total_points}</div>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <div className="text-sm text-gray-500">Техника с данными</div>
              <div className="text-2xl font-bold">{stats.vehicles_with_data}</div>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <div className="text-sm text-gray-500">Последняя точка</div>
              <div className="text-sm font-medium">{formatDate(stats.latest_recorded_at)}</div>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <div className="text-sm text-gray-500">Первая точка</div>
              <div className="text-sm font-medium">{formatDate(stats.oldest_recorded_at)}</div>
            </div>
          </div>
        )}

        {/* Vehicles Table */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="px-6 py-4 border-b">
            <h2 className="text-lg font-semibold">Техника и GPS-провайдеры</h2>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left font-medium text-gray-500">Название</th>
                <th className="px-6 py-3 text-left font-medium text-gray-500">Провайдер</th>
                <th className="px-6 py-3 text-left font-medium text-gray-500">Точек</th>
                <th className="px-6 py-3 text-left font-medium text-gray-500">Последняя точка</th>
                <th className="px-6 py-3 text-left font-medium text-gray-500">Действия</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {vehicles.map((v) => (
                <tr key={v.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 font-medium">{v.name}</td>
                  <td className="px-6 py-4">
                    {editingId === v.id ? (
                      <select
                        value={editProvider}
                        onChange={(e) => setEditProvider(e.target.value)}
                        className="border rounded px-2 py-1 text-sm"
                      >
                        <option value="">Не выбрано</option>
                        <option value="mapix">Mapix</option>
                        <option value="wialon">Wialon</option>
                      </select>
                    ) : (
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        v.gps_provider
                          ? 'bg-green-100 text-green-800'
                          : 'bg-gray-100 text-gray-800'
                      }`}>
                        {v.gps_provider || 'Нет'}
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-4">{v.total_points}</td>
                  <td className="px-6 py-4 text-gray-500">{formatDate(v.last_point_at)}</td>
                  <td className="px-6 py-4">
                    {editingId === v.id ? (
                      <div className="space-y-2">
                        <input
                          placeholder="Login"
                          value={editLogin}
                          onChange={(e) => setEditLogin(e.target.value)}
                          className="border rounded px-2 py-1 text-sm w-32"
                        />
                        <input
                          placeholder="Password"
                          type="password"
                          value={editPassword}
                          onChange={(e) => setEditPassword(e.target.value)}
                          className="border rounded px-2 py-1 text-sm w-32"
                        />
                        <input
                          placeholder="API URL"
                          value={editApiUrl}
                          onChange={(e) => setEditApiUrl(e.target.value)}
                          className="border rounded px-2 py-1 text-sm w-48"
                        />
                        <div className="flex gap-2">
                          <button
                            onClick={() => saveConfig(v.id)}
                            className="bg-blue-600 text-white px-3 py-1 rounded text-xs hover:bg-blue-700"
                          >
                            Сохранить
                          </button>
                          <button
                            onClick={() => setEditingId(null)}
                            className="bg-gray-200 text-gray-700 px-3 py-1 rounded text-xs hover:bg-gray-300"
                          >
                            Отмена
                          </button>
                        </div>
                      </div>
                    ) : (
                      <button
                        onClick={() => startEdit(v)}
                        className="text-blue-600 hover:text-blue-800 text-xs font-medium"
                      >
                        Настроить
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Layout>
  );
}