import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { reconciliationApi } from '../api/reconciliation';
import { financeApi, type PayoutsSummary } from '../api/finance';

export const DashboardWidgets: React.FC = () => {
  const navigate = useNavigate();
  const [reconciliationStats, setReconciliationStats] = useState({
    manual_review: 0,
    pending: 0,
  });
  const [payoutsSummary, setPayoutsSummary] = useState<PayoutsSummary | null>(null);

  useEffect(() => {
    loadWidgetsData();
  }, []);

  const loadWidgetsData = async () => {
    // Загружаем статистику сверок
    try {
      const stats = await reconciliationApi.getStats();
      setReconciliationStats({
        manual_review: stats.manual_review || 0,
        pending: stats.pending || 0,
      });
    } catch (err) {
      console.error('Failed to load reconciliation stats:', err);
    }

    // Загружаем сводку по выплатам (текущий месяц)
    try {
      const now = new Date();
      const dateFrom = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().split('T')[0];
      const dateTo = new Date(now.getFullYear(), now.getMonth() + 1, 0).toISOString().split('T')[0];
      const summary = await financeApi.getPayoutsSummary(dateFrom, dateTo);
      setPayoutsSummary(summary);
    } catch (err) {
      console.error('Failed to load payouts summary:', err);
    }
  };

  const formatMoney = (v: number) => {
    return v.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
      {/* Виджет 1: Сверки требуют внимания */}
      <div
        onClick={() => navigate('/reconciliation')}
        className="bg-white rounded-lg shadow hover:shadow-lg transition-shadow cursor-pointer p-6 border-l-4 border-orange-500"
      >
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium text-gray-500">Сверки требуют внимания</h3>
          <span className="text-3xl">⚠️</span>
        </div>
        <div className="text-3xl font-bold text-orange-600 mb-2">
          {reconciliationStats.manual_review}
        </div>
        <div className="text-sm text-gray-600">
          Ручная проверка расхождений
        </div>
        <div className="mt-3 text-xs text-blue-600 hover:text-blue-800">
          Перейти к сверкам →
        </div>
      </div>

      {/* Виджет 2: Ожидают выплаты */}
      <div
        onClick={() => navigate('/finance')}
        className="bg-white rounded-lg shadow hover:shadow-lg transition-shadow cursor-pointer p-6 border-l-4 border-green-500"
      >
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium text-gray-500">Ожидают выплаты</h3>
          <span className="text-3xl">💸</span>
        </div>
        <div className="text-3xl font-bold text-green-600 mb-2">
          {payoutsSummary ? formatMoney(payoutsSummary.pending_payouts ? payoutsSummary.total_net : 0) : '—'} ₽
        </div>
        <div className="text-sm text-gray-600">
          За текущий месяц
        </div>
        <div className="mt-3 text-xs text-blue-600 hover:text-blue-800">
          Перейти к финансам →
        </div>
      </div>

      {/* Виджет 3: Быстрые действия */}
      <div className="bg-white rounded-lg shadow p-6 border-l-4 border-blue-500">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium text-gray-500">Быстрые действия</h3>
          <span className="text-3xl">⚡</span>
        </div>
        <div className="space-y-2">
          <button
            onClick={() => navigate('/reconciliation')}
            className="w-full text-left px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 rounded transition-colors"
          >
            📊 Открыть сверки
          </button>
          <button
            onClick={() => navigate('/invoices')}
            className="w-full text-left px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 rounded transition-colors"
          >
            📄 Создать счёт
          </button>
          <button
            onClick={() => navigate('/finance')}
            className="w-full text-left px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 rounded transition-colors"
          >
            💰 Batch выплаты
          </button>
        </div>
      </div>
    </div>
  );
};

export default DashboardWidgets;
