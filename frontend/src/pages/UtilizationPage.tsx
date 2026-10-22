import React, { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import apiClient from '../api/client';

const UtilizationPage: React.FC = () => {
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [dateFrom, setDateFrom] = useState(() => {
    const d = new Date(); d.setDate(1); return d.toISOString().slice(0, 10);
  });
  const [dateTo, setDateTo] = useState(() => new Date().toISOString().slice(0, 10));

  const loadStats = async () => {
    try {
      setLoading(true);
      const res = await apiClient.get('/shifts/stats/utilization', { params: { date_from: dateFrom, date_to: dateTo } });
      setStats(res.data);
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  };

  useEffect(() => { loadStats(); }, [dateFrom, dateTo]);

  const getColor = (pct: number) => pct >= 80 ? 'bg-green-500' : pct >= 50 ? 'bg-yellow-500' : 'bg-red-500';

  return (
    <Layout>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
          <h1 className="text-2xl font-bold text-gray-900">📊 Утилизация техники</h1>
          <button onClick={() => window.open(`/api/v1/shifts/stats/utilization/export?date_from=${dateFrom}&date_to=${dateTo}`, '_blank')}
            className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 text-sm font-medium flex items-center gap-2">
            📥 Экспорт Excel
          </button>
          <button onClick={() => window.open(`/api/v1/shifts/export/1c-acts?date_from=${dateFrom}&date_to=${dateTo}`, '_blank')}
            className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 text-sm font-medium flex items-center gap-2">
            🏢 Выгрузка 1С
          </button>
        </div>
          <div className="flex gap-3 items-center">
            <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} className="px-3 py-2 border rounded-lg text-sm" />
            <span className="text-gray-400">—</span>
            <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} className="px-3 py-2 border rounded-lg text-sm" />
          </div>
        </div>

        {loading ? (
          <div className="flex justify-center py-12"><div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600"></div></div>
        ) : stats ? (
          <>
            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="bg-white rounded-xl shadow-sm p-5 border-l-4 border-blue-500">
                <p className="text-sm text-gray-500">Техники</p>
                <p className="text-2xl font-bold text-gray-900">{stats.summary.total_vehicles}</p>
              </div>
              <div className="bg-white rounded-xl shadow-sm p-5 border-l-4 border-green-500">
                <p className="text-sm text-gray-500">Ср. утилизация</p>
                <p className="text-2xl font-bold text-gray-900">{stats.summary.avg_utilization_pct}%</p>
              </div>
              <div className="bg-white rounded-xl shadow-sm p-5 border-l-4 border-purple-500">
                <p className="text-sm text-gray-500">Всего смен</p>
                <p className="text-2xl font-bold text-gray-900">{stats.summary.total_shifts}</p>
              </div>
              <div className="bg-white rounded-xl shadow-sm p-5 border-l-4 border-orange-500">
                <p className="text-sm text-gray-500">Часов работы</p>
                <p className="text-2xl font-bold text-gray-900">{stats.summary.total_hours}ч</p>
              </div>
            </div>

            {/* Vehicle Table */}
            <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Техника</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Утилизация</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Активные дни</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Смен</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Часов</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {stats.vehicles.map((v: any) => (
                    <tr key={v.vehicle_id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">{v.vehicle_name}</td>
                      <td className="px-4 py-3 text-sm">
                        <div className="flex items-center gap-2">
                          <div className="w-24 bg-gray-200 rounded-full h-2">
                            <div className={`h-2 rounded-full ${getColor(v.utilization_pct)}`} style={{ width: `${Math.min(v.utilization_pct, 100)}%` }}></div>
                          </div>
                          <span className="text-xs font-medium">{v.utilization_pct}%</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">{v.active_days} / {v.total_days}</td>
                      <td className="px-4 py-3 text-sm text-gray-600">{v.shift_count}</td>
                      <td className="px-4 py-3 text-sm text-gray-600">{v.total_hours}ч</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : <p className="text-gray-400 text-center py-8">Нет данных</p>}
      </div>
    </Layout>
  );
};

export default UtilizationPage;
