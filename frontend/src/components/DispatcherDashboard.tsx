import React, { useEffect, useState } from 'react';
import apiClient from '../api/client';

const DispatcherDashboard: React.FC = () => {
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient.get('/shifts/dashboard/daily-summary')
      .then(res => setSummary(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="animate-pulse h-32 bg-gray-100 rounded-xl"></div>;
  if (!summary) return null;

  const statusLabels: Record<string, string> = {
    planned: '⏳ Запланировано', confirmed: '✅ Подтверждено',
    in_progress: '🔧 В работе', completed: '🏁 Завершено', cancelled: '❌ Отменено',
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-gray-900">📋 Сводка на {new Date(summary.date).toLocaleDateString('ru-RU')}</h2>
        <span className="text-xs text-gray-400">Автообновление</span>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div className="bg-blue-50 rounded-lg p-3 text-center">
          <p className="text-2xl font-bold text-blue-700">{summary.today.total_shifts}</p>
          <p className="text-xs text-blue-600">Смен сегодня</p>
        </div>
        <div className="bg-orange-50 rounded-lg p-3 text-center">
          <p className="text-2xl font-bold text-orange-700">{summary.alerts.idle_vehicles}</p>
          <p className="text-xs text-orange-600">Простаивает</p>
        </div>
        <div className="bg-purple-50 rounded-lg p-3 text-center">
          <p className="text-2xl font-bold text-purple-700">{summary.alerts.pending_requests}</p>
          <p className="text-xs text-purple-600">Заявок в обработке</p>
        </div>
      </div>

      {/* Status breakdown */}
      <div className="space-y-1">
        {Object.entries(summary.today.status_breakdown).map(([status, count]) => (
          <div key={status} className="flex justify-between text-sm">
            <span>{statusLabels[status] || status}</span>
            <span className="font-medium">{count}</span>
          </div>
        ))}
      </div>

      {/* Idle vehicles alert */}
      {summary.today.idle_vehicle_names.length > 0 && (
        <div className="bg-red-50 border border-red-100 rounded-lg p-3">
          <p className="text-xs font-semibold text-red-700 mb-1">⚠️ Простаивающая техника:</p>
          <p className="text-xs text-red-600">{summary.today.idle_vehicle_names.join(', ')}</p>
        </div>
      )}

      {/* Tomorrow preview */}
      {summary.tomorrow.total_shifts > 0 && (
        <div className="border-t pt-3">
          <p className="text-xs font-semibold text-gray-500 mb-2">Завтра: {summary.tomorrow.total_shifts} смен</p>
          <div className="space-y-1">
            {summary.tomorrow.upcoming.slice(0, 5).map((u: any, i: number) => (
              <div key={i} className="text-xs text-gray-600 flex justify-between">
                <span>{u.vehicle_name}</span>
                <span className="text-gray-400">{u.start}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default DispatcherDashboard;
