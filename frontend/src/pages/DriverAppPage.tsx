import React, { useEffect, useState } from 'react';
import apiClient from '../api/client';

const DriverAppPage: React.FC = () => {
  const [shifts, setShifts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'today' | 'week'>('today');

  const loadShifts = async () => {
    try {
      const res = await apiClient.get('/drivers/my-shifts');
      setShifts(Array.isArray(res.data) ? res.data : res.data?.items || []);
    } catch {} finally { setLoading(false); }
  };

  useEffect(() => { loadShifts(); }, []);

  const today = new Date().toISOString().split('T')[0];
  const todayShifts = shifts.filter(s => s.shift_date === today);
  const weekShifts = shifts.slice(0, 10);

  const statusColors: Record<string, string> = {
    planned: 'bg-blue-100 text-blue-800', confirmed: 'bg-green-100 text-green-800',
    in_progress: 'bg-cyan-100 text-cyan-800', completed: 'bg-emerald-100 text-emerald-800',
  };
  const statusLabels: Record<string, string> = {
    planned: 'Запланировано', confirmed: 'Подтверждено',
    in_progress: 'В работе', completed: 'Завершено', cancelled: 'Отменено',
  };

  const startShift = async (taskId: number) => {
    try {
      await apiClient.post(`/drivers/shifts/${taskId}/start`);
      loadShifts();
    } catch (err: any) { alert('Ошибка: ' + (err.response?.data?.detail || '')); }
  };

  return (
    <div className="min-h-screen bg-gray-50 pb-20">
      {/* Header */}
      <div className="bg-blue-600 text-white p-4 sticky top-0 z-10 shadow-md">
        <h1 className="text-lg font-bold">🚛 Мои смены</h1>
        <p className="text-xs opacity-80">{new Date().toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' })}</p>
      </div>

      {/* Tabs */}
      <div className="flex border-b bg-white sticky top-[72px] z-10">
        <button onClick={() => setActiveTab('today')}
          className={`flex-1 py-3 text-sm font-medium ${activeTab === 'today' ? 'text-blue-600 border-b-2 border-blue-600' : 'text-gray-500'}`}>
          Сегодня ({todayShifts.length})
        </button>
        <button onClick={() => setActiveTab('week')}
          className={`flex-1 py-3 text-sm font-medium ${activeTab === 'week' ? 'text-blue-600 border-b-2 border-blue-600' : 'text-gray-500'}`}>
          Неделя
        </button>
      </div>

      {/* Content */}
      <div className="p-4 space-y-3">
        {loading ? (
          <div className="flex justify-center py-12"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div></div>
        ) : (activeTab === 'today' ? todayShifts : weekShifts).length === 0 ? (
          <div className="text-center py-12 text-gray-400">
            <p className="text-4xl mb-2">😴</p>
            <p>Нет смен на {activeTab === 'today' ? 'сегодня' : 'этот период'}</p>
          </div>
        ) : (
          (activeTab === 'today' ? todayShifts : weekShifts).map((s: any) => (
            <div key={s.id} className="bg-white rounded-xl shadow-sm border p-4 space-y-2">
              <div className="flex justify-between items-start">
                <div>
                  <p className="font-bold text-gray-900">{s.vehicle_name || 'Техника'}</p>
                  <p className="text-sm text-gray-500">{s.shift_date} • {s.planned_start ? new Date(s.planned_start).toLocaleTimeString('ru-RU', {hour:'2-digit',minute:'2-digit'}) : ''} — {s.planned_end ? new Date(s.planned_end).toLocaleTimeString('ru-RU', {hour:'2-digit',minute:'2-digit'}) : ''}</p>
                </div>
                <span className={`px-2 py-1 rounded-full text-xs font-medium ${statusColors[s.status] || 'bg-gray-100 text-gray-700'}`}>
                  {statusLabels[s.status] || s.status}
                </span>
              </div>
              {s.status === 'confirmed' && (
                <button onClick={() => startShift(s.id)}
                  className="w-full py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 active:bg-green-800">
                  ▶️ Начать смену
                </button>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default DriverAppPage;
