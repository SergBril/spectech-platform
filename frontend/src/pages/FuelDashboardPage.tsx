import React, { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import apiClient from '../api/client';

const FuelDashboardPage: React.FC = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [dateFrom, setDateFrom] = useState(() => {
    const d = new Date(); d.setDate(d.getDate() - 30); return d.toISOString().slice(0, 10);
  });
  const [dateTo, setDateTo] = useState(() => new Date().toISOString().slice(0, 10));

  useEffect(() => {
    setLoading(true);
    apiClient.get('/shifts/stats/fuel-dashboard', { params: { date_from: dateFrom, date_to: dateTo } })
      .then(res => setData(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [dateFrom, dateTo]);

  return (
    <Layout>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <h1 className="text-2xl font-bold text-gray-900">📊 Расход топлива</h1>
          <div className="flex gap-3 items-center">
            <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} className="px-3 py-2 border rounded-lg text-sm" />
            <span className="text-gray-400">—</span>
            <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} className="px-3 py-2 border rounded-lg text-sm" />
            <button onClick={() => window.open(`/api/v1/shifts/stats/fuel-consumption/export?date_from=${dateFrom}&date_to=${dateTo}`, '_blank')}
              className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 text-sm font-medium">📥 Excel</button>
          </div>
        </div>

        {loading ? (
          <div className="flex justify-center py-12"><div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600"></div></div>
        ) : data ? (
          <>
            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
              <div className="bg-white rounded-xl shadow-sm p-5 border-l-4 border-orange-500">
                <p className="text-sm text-gray-500">Всего литров</p>
                <p className="text-2xl font-bold text-gray-900">{data.summary.total_liters}</p>
              </div>
              <div className="bg-white rounded-xl shadow-sm p-5 border-l-4 border-blue-500">
                <p className="text-sm text-gray-500">Ср. в день</p>
                <p className="text-2xl font-bold text-gray-900">{data.summary.avg_daily_liters} л</p>
              </div>
              <div className="bg-white rounded-xl shadow-sm p-5 border-l-4 border-purple-500">
                <p className="text-sm text-gray-500">Заправок</p>
                <p className="text-2xl font-bold text-gray-900">{data.summary.total_entries}</p>
              </div>
              <div className="bg-white rounded-xl shadow-sm p-5 border-l-4 border-green-500">
                <p className="text-sm text-gray-500">Техники</p>
                <p className="text-2xl font-bold text-gray-900">{data.summary.vehicles_count}</p>
              </div>
              <div className={`bg-white rounded-xl shadow-sm p-5 border-l-4 ${data.summary.anomalies_count > 0 ? 'border-red-500' : 'border-gray-300'}`}>
                <p className="text-sm text-gray-500">Аномалий</p>
                <p className={`text-2xl font-bold ${data.summary.anomalies_count > 0 ? 'text-red-600' : 'text-gray-900'}`}>{data.summary.anomalies_count}</p>
              </div>
            </div>

            {/* Daily Trend Bar Chart (CSS-only) */}
            <div className="bg-white rounded-xl shadow-sm border p-5">
              <h2 className="text-lg font-bold text-gray-900 mb-4">📈 Ежедневный расход</h2>
              <div className="flex items-end gap-1 h-40">
                {data.daily_trend.map((d: any, i: number) => {
                  const maxL = Math.max(...data.daily_trend.map((x: any) => x.liters), 1);
                  const h = Math.max((d.liters / maxL) * 100, 2);
                  return (
                    <div key={i} className="flex-1 flex flex-col items-center group relative">
                      <div className="absolute bottom-full mb-1 hidden group-hover:block bg-gray-800 text-white text-xs px-2 py-1 rounded whitespace-nowrap z-10">
                        {d.date}: {d.liters} л
                      </div>
                      <div className="w-full bg-orange-400 rounded-t hover:bg-orange-500 transition-colors" style={{ height: `${h}%` }}></div>
                    </div>
                  );
                })}
              </div>
              <div className="flex justify-between mt-2 text-xs text-gray-400">
                <span>{data.daily_trend[0]?.date}</span>
                <span>{data.daily_trend[data.daily_trend.length - 1]?.date}</span>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Anomalies */}
              <div className="bg-white rounded-xl shadow-sm border p-5">
                <h2 className="text-lg font-bold text-gray-900 mb-3">🔴 Аномалии расхода</h2>
                {data.anomalies.length === 0 ? (
                  <p className="text-gray-400 text-sm py-4 text-center">Нет аномалий ✅</p>
                ) : (
                  <div className="space-y-2 max-h-64 overflow-y-auto">
                    {data.anomalies.map((a: any, i: number) => (
                      <div key={i} className="flex items-center justify-between p-3 bg-red-50 rounded-lg border border-red-100 text-sm">
                        <div>
                          <span className="font-medium">{a.vehicle_name}</span>
                          <span className="text-gray-500 ml-2">{a.date}</span>
                        </div>
                        <div className="text-right">
                          <span className="font-bold text-red-700">{a.liters} л</span>
                          <span className="text-xs text-red-500 ml-1">(+{a.deviation_pct}%)</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Top Consumers */}
              <div className="bg-white rounded-xl shadow-sm border p-5">
                <h2 className="text-lg font-bold text-gray-900 mb-3">🏆 Топ потребителей</h2>
                <div className="space-y-2">
                  {data.top_consumers.map((c: any, i: number) => {
                    const maxL = Math.max(...data.top_consumers.map((x: any) => x.total_liters), 1);
                    const w = (c.total_liters / maxL) * 100;
                    return (
                      <div key={i} className="flex items-center gap-3">
                        <span className="text-xs text-gray-400 w-4">{i + 1}</span>
                        <div className="flex-1">
                          <div className="flex justify-between text-sm mb-1">
                            <span className="font-medium">{c.vehicle_name}</span>
                            <span className="text-gray-600">{c.total_liters} л</span>
                          </div>
                          <div className="w-full bg-gray-100 rounded-full h-2">
                            <div className="bg-orange-500 h-2 rounded-full" style={{ width: `${w}%` }}></div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </>
        ) : <p className="text-gray-400 text-center py-8">Нет данных</p>}
      </div>
    </Layout>
  );
};

export default FuelDashboardPage;
