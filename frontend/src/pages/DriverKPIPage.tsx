import React, { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import apiClient from '../api/client';

const DriverKPIPage: React.FC = () => {
  const [kpi, setKpi] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [dateFrom, setDateFrom] = useState(() => {
    const d = new Date(); d.setDate(1); return d.toISOString().slice(0, 10);
  });
  const [dateTo, setDateTo] = useState(() => new Date().toISOString().slice(0, 10));

  useEffect(() => {
    setLoading(true);
    apiClient.get('/shifts/stats/driver-kpi', { params: { date_from: dateFrom, date_to: dateTo } })
      .then(res => setKpi(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [dateFrom, dateTo]);

  const getRatingColor = (r: number) => r >= 70 ? 'text-green-700 bg-green-50' : r >= 40 ? 'text-yellow-700 bg-yellow-50' : 'text-red-700 bg-red-50';

  return (
    <Layout>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">📊 KPI Водителей</h1>
          <div className="flex gap-3 items-center">
            <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} className="px-3 py-2 border rounded-lg text-sm" />
            <span className="text-gray-400">—</span>
            <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} className="px-3 py-2 border rounded-lg text-sm" />
          </div>
        </div>

        {loading ? (
          <div className="flex justify-center py-12"><div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600"></div></div>
        ) : kpi ? (
          <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">#</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Водитель</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Рейтинг</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Смен</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Утилизация</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Часов</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Завершение %</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {kpi.drivers.map((d: any, i: number) => (
                  <tr key={d.driver_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm text-gray-500">{i + 1}</td>
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">{d.driver_name}</td>
                    <td className="px-4 py-3 text-sm">
                      <span className={`px-2 py-1 rounded-full text-xs font-bold ${getRatingColor(d.rating)}`}>{d.rating}</span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">{d.shift_count}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">{d.utilization_pct}%</td>
                    <td className="px-4 py-3 text-sm text-gray-600">{d.total_hours}ч</td>
                    <td className="px-4 py-3 text-sm text-gray-600">{d.completion_rate}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <p className="text-gray-400 text-center py-8">Нет данных</p>}
      </div>
    </Layout>
  );
};

export default DriverKPIPage;
