import React, { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import apiClient from '../api/client';

const FinanceDashboardPage: React.FC = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [year, setYear] = useState(new Date().getFullYear());

  useEffect(() => {
    setLoading(true);
    apiClient.get('/shifts/stats/finance-dashboard', { params: { year } })
      .then(res => setData(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [year]);

  const fmt = (n: number) => n.toLocaleString('ru-RU');

  return (
    <Layout>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-4">
            <h1 className="text-2xl font-bold text-gray-900">💰 Финансовый дашборд</h1>
            <button onClick={() => window.open(`/api/v1/shifts/stats/finance-dashboard/export?year=${year}`, '_blank')}
              className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 text-sm font-medium">📥 Excel</button>
          </div>
          <select value={year} onChange={e => setYear(Number(e.target.value))}
            className="px-3 py-2 border rounded-lg text-sm">
            {[2024, 2025, 2026, 2027].map(y => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>

        {loading ? (
          <div className="flex justify-center py-12"><div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600"></div></div>
        ) : data ? (
          <>
            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="bg-white rounded-xl shadow-sm p-5 border-l-4 border-green-500">
                <p className="text-sm text-gray-500">Выручка</p>
                <p className="text-2xl font-bold text-green-700">{fmt(data.summary.total_revenue)} ₽</p>
              </div>
              <div className="bg-white rounded-xl shadow-sm p-5 border-l-4 border-red-500">
                <p className="text-sm text-gray-500">Расходы</p>
                <p className="text-2xl font-bold text-red-700">{fmt(data.summary.total_expenses)} ₽</p>
              </div>
              <div className={`bg-white rounded-xl shadow-sm p-5 border-l-4 ${data.summary.total_margin >= 0 ? 'border-blue-500' : 'border-orange-500'}`}>
                <p className="text-sm text-gray-500">Маржа</p>
                <p className={`text-2xl font-bold ${data.summary.total_margin >= 0 ? 'text-blue-700' : 'text-orange-700'}`}>{fmt(data.summary.total_margin)} ₽</p>
              </div>
              <div className="bg-white rounded-xl shadow-sm p-5 border-l-4 border-purple-500">
                <p className="text-sm text-gray-500">Рентабельность</p>
                <p className="text-2xl font-bold text-purple-700">{data.summary.total_margin_pct}%</p>
              </div>
            </div>

            {/* Monthly Chart (CSS bars) */}
            <div className="bg-white rounded-xl shadow-sm border p-5">
              <h2 className="text-lg font-bold text-gray-900 mb-4">📊 По месяцам {data.year}</h2>
              <div className="flex items-end gap-1 h-48">
                {data.months.map((m: any) => {
                  const maxVal = Math.max(...data.months.map((x: any) => Math.max(x.revenue, x.total_expenses)), 1);
                  const revH = Math.max((m.revenue / maxVal) * 100, 1);
                  const expH = Math.max((m.total_expenses / maxVal) * 100, 1);
                  return (
                    <div key={m.month} className="flex-1 flex flex-col items-center group relative">
                      <div className="absolute bottom-full mb-1 hidden group-hover:block bg-gray-800 text-white text-xs px-2 py-1 rounded whitespace-nowrap z-10">
                        {m.month_name}: Выручка {fmt(m.revenue)}₽ | Расходы {fmt(m.total_expenses)}₽ | Маржа {fmt(m.margin)}₽ ({m.margin_pct}%)
                      </div>
                      <div className="w-full flex gap-0.5 items-end h-full">
                        <div className="flex-1 bg-green-400 rounded-t hover:bg-green-500 transition-colors" style={{ height: `${revH}%` }}></div>
                        <div className="flex-1 bg-red-400 rounded-t hover:bg-red-500 transition-colors" style={{ height: `${expH}%` }}></div>
                      </div>
                      <span className="text-[10px] text-gray-400 mt-1">{m.month_name}</span>
                    </div>
                  );
                })}
              </div>
              <div className="flex gap-4 mt-3 text-xs">
                <span className="flex items-center gap-1"><span className="w-3 h-3 bg-green-400 rounded"></span> Выручка</span>
                <span className="flex items-center gap-1"><span className="w-3 h-3 bg-red-400 rounded"></span> Расходы</span>
              </div>
            </div>

            {/* Monthly Table */}
            <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Месяц</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Выручка</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Топливо</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Зарплата</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Амортизация</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Маржа</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">%</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {data.months.filter((m: any) => m.revenue > 0 || m.total_expenses > 0).map((m: any) => (
                    <tr key={m.month} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">{m.month_name}</td>
                      <td className="px-4 py-3 text-sm text-right text-green-700">{fmt(m.revenue)}</td>
                      <td className="px-4 py-3 text-sm text-right text-gray-600">{fmt(m.fuel_cost)}</td>
                      <td className="px-4 py-3 text-sm text-right text-gray-600">{fmt(m.wage_cost)}</td>
                      <td className="px-4 py-3 text-sm text-right text-gray-600">{fmt(m.amortization_cost)}</td>
                      <td className={`px-4 py-3 text-sm text-right font-bold ${m.margin >= 0 ? 'text-blue-700' : 'text-red-600'}`}>{fmt(m.margin)}</td>
                      <td className={`px-4 py-3 text-sm text-right ${m.margin_pct >= 0 ? 'text-blue-600' : 'text-red-500'}`}>{m.margin_pct}%</td>
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

export default FinanceDashboardPage;
