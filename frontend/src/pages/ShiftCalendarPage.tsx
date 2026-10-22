import React, { useEffect, useState, useCallback } from 'react';
import Layout from '../components/Layout';
import apiClient from '../api/client';
import { useWebSocket } from '../contexts/WebSocketContext';

interface ShiftTask {
  id: number;
  request_id: number | null;
  vehicle_id: number;
  vehicle_name: string;
  driver_id: number | null;
  driver_name: string | null;
  shift_date: string;
  planned_start: string | null;
  planned_end: string | null;
  status: string;
}

const STATUS_COLORS: Record<string, string> = {
  planned: 'bg-blue-100 border-blue-300 text-blue-800',
  confirmed: 'bg-green-100 border-green-300 text-green-800',
  in_progress: 'bg-cyan-100 border-cyan-300 text-cyan-800',
  completed: 'bg-emerald-100 border-emerald-300 text-emerald-800',
  cancelled: 'bg-red-100 border-red-300 text-red-800',
};

const DAYS_RU = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

const ShiftCalendarPage: React.FC = () => {
  const [shifts, setShifts] = useState<ShiftTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [currentWeek, setCurrentWeek] = useState(new Date());
  const [draggedShift, setDraggedShift] = useState<number | null>(null);

  // Live updates via WebSocket
  const wsMessage = useWebSocket();
  useEffect(() => {
    if (wsMessage && wsMessage.type === 'shift_updated') {
      setShifts(prev => prev.map(s =>
        s.id === wsMessage.task_id
          ? { ...s, shift_date: wsMessage.shift_date, status: wsMessage.status || s.status }
          : s
      ));
    }
  }, [wsMessage]);

  const getWeekStart = (date: Date) => {
    const d = new Date(date);
    const day = d.getDay();
    const diff = d.getDate() - day + (day === 0 ? -6 : 1);
    return new Date(d.setDate(diff));
  };

  const weekStart = getWeekStart(currentWeek);
  const weekDays = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(weekStart);
    d.setDate(d.getDate() + i);
    return d.toISOString().split('T')[0];
  });

  const loadShifts = useCallback(async () => {
    try {
      const res = await apiClient.get('/shifts', {
        params: { date_from: weekDays[0], date_to: weekDays[6] },
      });
      setShifts(Array.isArray(res.data) ? res.data : res.data?.items || []);
    } catch (err) {
      console.error('Failed to load shifts:', err);
    } finally {
      setLoading(false);
    }
  }, [weekDays[0], weekDays[6]]);

  useEffect(() => { loadShifts(); }, [loadShifts]);

  const handleDragStart = (shiftId: number) => {
    setDraggedShift(shiftId);
  };

  const handleDrop = async (targetDate: string) => {
    if (!draggedShift) return;
    try {
      await apiClient.put(`/shifts/${draggedShift}`, { shift_date: targetDate });
      setShifts(prev => prev.map(s => s.id === draggedShift ? { ...s, shift_date: targetDate } : s));
    } catch (err: any) {
      alert('Ошибка переноса: ' + (err.response?.data?.detail || ''));
    } finally {
      setDraggedShift(null);
    }
  };

  const prevWeek = () => {
    const d = new Date(currentWeek);
    d.setDate(d.getDate() - 7);
    setCurrentWeek(d);
  };

  const nextWeek = () => {
    const d = new Date(currentWeek);
    d.setDate(d.getDate() + 7);
    setCurrentWeek(d);
  };

  // Group vehicles
  const vehicles = [...new Set(shifts.map(s => `${s.vehicle_id}:${s.vehicle_name}`))];

  return (
    <Layout>
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-gray-900">📅 Планирование смен</h1>
          <div className="flex items-center gap-3">
            <button onClick={prevWeek} className="px-3 py-1.5 border rounded-lg hover:bg-gray-50">← Неделя</button>
            <span className="text-sm font-medium text-gray-700">
              {new Date(weekDays[0]).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })} —{' '}
              {new Date(weekDays[6]).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })}
            </span>
            <button onClick={nextWeek} className="px-3 py-1.5 border rounded-lg hover:bg-gray-50">Неделя →</button>
            <button onClick={() => window.open(`/api/v1/shifts/calendar/export-pdf?date_from=${weekDays[0]}&date_to=${weekDays[6]}`, '_blank')}
              className="px-3 py-1.5 bg-gray-800 text-white rounded-lg hover:bg-gray-900 text-sm font-medium flex items-center gap-1">
              🖨️ Печать PDF
            </button>
          </div>
        </div>

        {loading ? (
          <div className="flex justify-center py-12"><div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600"></div></div>
        ) : (
          <div className="overflow-x-auto bg-white rounded-xl shadow-sm border">
            <table className="min-w-full border-collapse">
              <thead>
                <tr>
                  <th className="sticky left-0 z-10 bg-gray-50 border p-3 text-left text-xs font-medium text-gray-500 uppercase min-w-[180px]">Техника</th>
                  {weekDays.map((day, i) => (
                    <th key={day} className="border p-3 text-center text-xs font-medium text-gray-500 uppercase min-w-[120px]">
                      <div>{DAYS_RU[i]}</div>
                      <div className="text-gray-400">{new Date(day).getDate()}</div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {vehicles.length === 0 ? (
                  <tr><td colSpan={8} className="text-center py-8 text-gray-400">Нет смен на этой неделе. Перетащите смены из заявок.</td></tr>
                ) : vehicles.map(v => {
                  const [vid, vname] = v.split(':');
                  return (
                    <tr key={vid}>
                      <td className="sticky left-0 z-10 bg-white border p-3 text-sm font-medium text-gray-900">{vname}</td>
                      {weekDays.map(day => {
                        const dayShifts = shifts.filter(s => String(s.vehicle_id) === vid && s.shift_date === day);
                        return (
                          <td key={day} className="border p-1 align-top min-h-[80px]"
                            onDragOver={e => e.preventDefault()}
                            onDrop={() => handleDrop(day)}>
                            {dayShifts.map(shift => (
                              <div key={shift.id} draggable
                                onDragStart={() => handleDragStart(shift.id)}
                                className={`p-2 mb-1 rounded border cursor-grab active:cursor-grabbing text-xs ${STATUS_COLORS[shift.status] || 'bg-gray-100 border-gray-300'}`}>
                                <div className="font-medium">{shift.driver_name || 'Без водителя'}</div>
                                <div className="opacity-75">{shift.planned_start ? new Date(shift.planned_start).toLocaleTimeString('ru-RU', {hour:'2-digit',minute:'2-digit'}) : ''}</div>
                              </div>
                            ))}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default ShiftCalendarPage;
