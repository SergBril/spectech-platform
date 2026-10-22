import React, { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import apiClient from '../api/client';

const PlatformOverviewPage: React.FC = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient.get('/shifts/stats/platform-overview')
      .then(res => setData(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const fmt = (n: number) => n.toLocaleString('ru-RU');

  return (
    <Layout>
      <div className="p-6 space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">🏢 Обзор платформы</h1>

        {loading ? (
          <div className="flex justify-center py-12"><div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600"></div></div>
        ) : data ? (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-white rounded-xl shadow-sm p-5 border-l-4 border-blue-500">
                <p className="text-sm text-gray-500">Пользователей</p>
                <p className="text-2xl font-bold text-gray-900">{data.users.total}</p>
                <p className="text-xs text-gray-400">Водителей: {data.users.drivers}</p>
              </div>
              <div className="bg-white rounded-xl shadow-sm p-5 border-l-4 border-purple-500">
                <p className="text-sm text-gray-500">Техники</p>
                <p className="text-2xl font-bold text-gray-900">{data.vehicles.total}</p>
              </div>
              <div className="bg-white rounded-xl shadow-sm p-5 border-l-4 border-green-500">
                <p className="text-sm text-gray-500">Акты за месяц</p>
                <p className="text-2xl font-bold text-green-700">{fmt(data.acts_this_month.revenue)} ₽</p>
                <p className="text-xs text-gray-400">{data.acts_this_month.count} актов</p>
              </div>
              <div className={`bg-white rounded-xl shadow-sm p-5 border-l-4 ${data.overdue_acts > 0 ? 'border-red-500' : 'border-green-500'}`}>
                <p className="text-sm text-gray-500">Просроченных актов</p>
                <p className={`text-2xl font-bold ${data.overdue_acts > 0 ? 'text-red-700' : 'text-green-700'}`}>{data.overdue_acts}</p>
              </div>
              <div className="bg-white rounded-xl shadow-sm p-5 border-l-4 border-orange-500">
                <p className="text-sm text-gray-500">Транзакции за месяц</p>
                <p className="text-2xl font-bold text-orange-700">{fmt(data.transactions_this_month.amount)} ₽</p>
                <p className="text-xs text-gray-400">{data.transactions_this_month.count} операций</p>
              </div>
              <div className={`bg-white rounded-xl shadow-sm p-5 border-l-4 ${data.unmatched_transactions > 0 ? 'border-yellow-500' : 'border-green-500'}`}>
                <p className="text-sm text-gray-500">Неразнесённых</p>
                <p className={`text-2xl font-bold ${data.unmatched_transactions > 0 ? 'text-yellow-700' : 'text-green-700'}`}>{data.unmatched_transactions}</p>
              </div>
              <div className="bg-white rounded-xl shadow-sm p-5 border-l-4 border-indigo-500">
                <p className="text-sm text-gray-500">Документов в архиве</p>
                <p className="text-2xl font-bold text-indigo-700">{data.documents_in_archive}</p>
              </div>
              <div className="bg-white rounded-xl shadow-sm p-5 border-l-4 border-cyan-500">
                <p className="text-sm text-gray-500">Смен сегодня</p>
                <p className="text-2xl font-bold text-cyan-700">{data.shifts_today}</p>
              </div>
            </div>
          </>
        ) : <p className="text-gray-400 text-center py-8">Нет данных</p>}
      </div>
    </Layout>
  );
};

export default PlatformOverviewPage;
