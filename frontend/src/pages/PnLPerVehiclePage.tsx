import React, { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import apiClient from '../api/client';

const PnLPerVehiclePage: React.FC = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [dateFrom, setDateFrom] = useState(() => { const d = new Date(); d.setDate(1); return d.toISOString().slice(0, 10); });
  const [dateTo, setDateTo] = useState(() => new Date().toISOString().slice(0, 10));

  useEffect(() => {
    setLoading(true);
    apiClient.get('/shifts/stats/pnl-per-vehicle', { params: { date_from: dateFrom, date_to: dateTo } })
      .then(res => setData(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [dateFrom, dateTo]);

  const fmt = (n: number) => n.toLocaleString('ru-RU');

  return (
    <Layout>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <h1 className="text-2xl font-bold text-gray-900">📊 Прибыльность по технике</h1>
          <div className="flex gap-3 items-center">
            <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} className="px-3 py-2 border rounded-lg text-sm" />
            <span className="text-gray-400">—</span>
            <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} className="px-3 py-2 border rounded-lg text-sm" />
          </div>
        </div>

        {loading ? (
          <div className="flex justify-center py-12"><div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600"></div></div>
        ) : data ? (
          <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Техника</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Часов</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Выручка</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Топливо</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Зарплата</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Амортизация</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Маржа</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">%</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {data.vehicles.filter((v: any) => v.hours > 0 || v.revenue > 0).map((v: any) => (
                  <tr key={v.vehicle_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">{v.vehicle_name}</td>
                    <td className="px-4 py-3 text-sm text-right text-gray-600">{v.hours}</td>
                    <td className="px-4 py-3 text-sm text-right text-green-700">{fmt(v.revenue)}</td>
                    <td className="px-4 py-3 text-sm text-right text-gray-600">{fmt(v.fuel_cost)}</td>
                    <td className="px-4 py-3 text-sm text-right text-gray-600">{fmt(v.wage_cost)}</td>
                    <td className="px-4 py-3 text-sm text-right text-gray-600">{fmt(v.amortization_cost)}</td>
                    <td className={`px-4 py-3 text-sm text-right font-bold ${v.margin >= 0 ? 'text-blue-700' : 'text-red-600'}`}>{fmt(v.margin)}</td>
                    <td className={`px-4 py-3 text-sm text-right ${v.margin_pct >= 0 ? 'text-blue-600' : 'text-red-500'}`}>{v.margin_pct}%</td>
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

export default PnLPerVehiclePage;
