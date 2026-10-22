import React, { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import apiClient from '../api/client';

const ReceivablesPage: React.FC = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient.get('/shifts/stats/receivables')
      .then(res => setData(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const fmt = (n: number) => n.toLocaleString('ru-RU');
  const bucketLabels: Record<string, string> = {
    current: 'Текущие (≤30д)', '1_30': '31-60 дней', '31_60': '61-90 дней', '61_90': '91-120 дней', '90_plus': '>120 дней',
  };
  const bucketColors: Record<string, string> = {
    current: 'bg-green-400', '1_30': 'bg-yellow-400', '31_60': 'bg-orange-400', '61_90': 'bg-red-400', '90_plus': 'bg-red-700',
  };

  return (
    <Layout>
      <div className="p-6 space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">💸 Дебиторская задолженность</h1>

        {loading ? (
          <div className="flex justify-center py-12"><div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600"></div></div>
        ) : data ? (
          <>
            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="bg-white rounded-xl shadow-sm p-5 border-l-4 border-blue-500">
                <p className="text-sm text-gray-500">Всего задолженность</p>
                <p className="text-2xl font-bold text-gray-900">{fmt(data.summary.total_outstanding)} ₽</p>
              </div>
              <div className={`bg-white rounded-xl shadow-sm p-5 border-l-4 ${data.summary.overdue_amount > 0 ? 'border-red-500' : 'border-green-500'}`}>
                <p className="text-sm text-gray-500">Просрочено</p>
                <p className={`text-2xl font-bold ${data.summary.overdue_amount > 0 ? 'text-red-700' : 'text-green-700'}`}>{fmt(data.summary.overdue_amount)} ₽</p>
              </div>
              <div className="bg-white rounded-xl shadow-sm p-5 border-l-4 border-orange-500">
                <p className="text-sm text-gray-500">Просроченных актов</p>
                <p className="text-2xl font-bold text-orange-700">{data.summary.overdue_count}</p>
              </div>
              <div className="bg-white rounded-xl shadow-sm p-5 border-l-4 border-green-500">
                <p className="text-sm text-gray-500">В срок</p>
                <p className="text-2xl font-bold text-green-700">{fmt(data.summary.on_time_amount)} ₽</p>
              </div>
            </div>

            {/* Ageing Buckets Bar */}
            <div className="bg-white rounded-xl shadow-sm border p-5">
              <h2 className="text-lg font-bold text-gray-900 mb-4">📊 Возрастная структура</h2>
              <div className="flex h-10 rounded-lg overflow-hidden">
                {Object.entries(data.ageing_buckets).map(([key, val]) => {
                  const total = Object.values(data.ageing_buckets).reduce((a: number, b: any) => a + Number(b), 0) || 1;
                  const pct = ((val as number) / total) * 100;
                  if (pct < 1) return null;
                  return (
                    <div key={key} className={`${bucketColors[key]} flex items-center justify-center text-white text-xs font-medium hover:opacity-90 transition-opacity`}
                      style={{ width: `${pct}%` }} title={`${bucketLabels[key]}: ${fmt(val as number)} ₽`}>
                      {pct > 8 ? `${Math.round(pct)}%` : ''}
                    </div>
                  );
                })}
              </div>
              <div className="flex gap-4 mt-3 text-xs flex-wrap">
                {Object.entries(bucketLabels).map(([key, label]) => (
                  <span key={key} className="flex items-center gap-1">
                    <span className={`w-3 h-3 rounded ${bucketColors[key]}`}></span>
                    {label}: {fmt(data.ageing_buckets[key])} ₽
                  </span>
                ))}
              </div>
            </div>

            {/* Overdue Acts Table */}
            <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
              <div className="px-4 py-3 bg-gray-50 border-b">
                <h2 className="text-sm font-bold text-gray-900">🔴 Просроченные акты ({data.overdue_acts.length})</h2>
              </div>
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Акт</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Дата</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Техника</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Контрагент</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Долг</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Просрочка</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {data.overdue_acts.length === 0 ? (
                    <tr><td colSpan={6} className="px-4 py-8 text-center text-green-600 text-sm font-medium">✅ Нет просроченных актов!</td></tr>
                  ) : data.overdue_acts.map((a: any) => (
                    <tr key={a.id} className={`hover:bg-gray-50 ${a.days_overdue > 60 ? 'bg-red-50' : ''}`}>
                      <td className="px-4 py-3 text-sm font-mono text-gray-700">{a.act_number}</td>
                      <td className="px-4 py-3 text-sm text-gray-600">{a.act_date}</td>
                      <td className="px-4 py-3 text-sm text-gray-900">{a.vehicle_name}</td>
                      <td className="px-4 py-3 text-sm text-gray-600">{a.counterparty || '—'}</td>
                      <td className="px-4 py-3 text-sm text-right font-bold text-red-700">{fmt(a.outstanding)} ₽</td>
                      <td className="px-4 py-3 text-sm text-right">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${a.days_overdue > 60 ? 'bg-red-100 text-red-700' : 'bg-orange-100 text-orange-700'}`}>
                          {a.days_overdue} дн.
                        </span>
                      </td>
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

export default ReceivablesPage;
