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
  const [showTemplateModal, setShowTemplateModal] = useState(false);
  const [templates, setTemplates] = useState<any[]>([]);
  const [templateForm, setTemplateForm] = useState({ vehicle_id: '', driver_id: '', weekday: 0, start_time: '08:00', end_time: '17:00' });
  const [exclusions, setExclusions] = useState<any[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | null>(null);
  const [exclusionDate, setExclusionDate] = useState('');
  const [exclusionReason, setExclusionReason] = useState('holiday');

  // Live updates via WebSocket
  const { subscribe } = useWebSocket();
  useEffect(() => {
    const unsubscribe = subscribe('shift_updated', (data: any) => {
      setShifts(prev => prev.map(s =>
        s.id === data.task_id
          ? { ...s, shift_date: data.shift_date, status: data.status || s.status }
          : s
      ));
    });
    return unsubscribe;
  }, [subscribe]);

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

  const loadTemplates = async () => {
    try {
      const res = await apiClient.get('/shifts/templates');
      setTemplates(Array.isArray(res.data) ? res.data : []);
    } catch { /* ignore */ }
  };

  const saveTemplate = async () => {
    try {
      await apiClient.post('/shifts/templates', {
        vehicle_id: parseInt(templateForm.vehicle_id),
        driver_id: templateForm.driver_id ? parseInt(templateForm.driver_id) : null,
        weekday: templateForm.weekday,
        start_time: templateForm.start_time,
        end_time: templateForm.end_time,
      });
      setShowTemplateModal(false);
      loadTemplates();
      alert('Шаблон создан');
    } catch (err: any) { alert('Ошибка: ' + (err.response?.data?.detail || '')); }
  };

  const loadExclusions = async (templateId: number) => {
    try {
      const res = await apiClient.get(`/shifts/templates/${templateId}/exclusions`);
      setExclusions(Array.isArray(res.data) ? res.data : []);
      setSelectedTemplateId(templateId);
    } catch { /* ignore */ }
  };

  const addExclusion = async () => {
    if (!selectedTemplateId || !exclusionDate) return;
    try {
      await apiClient.post(`/shifts/templates/${selectedTemplateId}/exclusions`, {
        exclusion_date: exclusionDate, reason: exclusionReason,
      });
      setExclusionDate('');
      loadExclusions(selectedTemplateId);
    } catch (err: any) { alert('Ошибка: ' + (err.response?.data?.detail || '')); }
  };

  const removeExclusion = async (id: number) => {
    try {
      await apiClient.delete(`/shifts/templates/exclusions/${id}`);
      if (selectedTemplateId) loadExclusions(selectedTemplateId);
    } catch (err: any) { alert('Ошибка: ' + (err.response?.data?.detail || '')); }
  };

  const deleteTemplate = async (id: number) => {
    if (!confirm('Удалить шаблон?')) return;
    try {
      await apiClient.delete(`/shifts/templates/${id}`);
      loadTemplates();
    } catch (err: any) { alert('Ошибка: ' + (err.response?.data?.detail || '')); }
  };

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
            <button onClick={() => window.open(`/api/v1/shifts/calendar/export-ical?date_from=${weekDays[0]}&date_to=${weekDays[6]}`, '_blank')}
              className="px-3 py-1.5 bg-orange-600 text-white rounded-lg hover:bg-orange-700 text-sm font-medium flex items-center gap-1">
              📅 iCal
            </button>
            <button onClick={async () => {
              if (!confirm('Применить шаблоны смен на эту неделю?')) return;
              try {
                const res = await apiClient.post('/shifts/templates/apply', { week_start: weekDays[0] });
                alert(`Создано смен: ${res.data.created}, пропущено: ${res.data.skipped}`);
                loadShifts();
              } catch (err: any) { alert('Ошибка: ' + (err.response?.data?.detail || '')); }
            }} className="px-3 py-1.5 bg-purple-600 text-white rounded-lg hover:bg-purple-700 text-sm font-medium flex items-center gap-1">
              🔄 Шаблоны
            </button>
            <button onClick={() => { setShowTemplateModal(true); loadTemplates(); }}
              className="px-3 py-1.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 text-sm font-medium flex items-center gap-1">
              ⚙️ Управление
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
      {/* Template Management Modal */}
      {showTemplateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full max-h-[85vh] overflow-y-auto">
            <div className="p-6 border-b flex justify-between items-center">
              <h2 className="text-xl font-bold text-gray-900">⚙️ Шаблоны смен</h2>
              <button onClick={() => setShowTemplateModal(false)} className="text-gray-400 hover:text-gray-600 text-xl">✕</button>
            </div>
            <div className="p-6 space-y-6">
              {/* Existing templates */}
              {templates.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-500 uppercase mb-3">Активные шаблоны</h3>
                  <div className="space-y-2">
                    {templates.map((t: any) => (
                      <div key={t.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border">
                        <div className="flex items-center gap-3">
                          <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs font-medium">{['Пн','Вт','Ср','Чт','Пт','Сб','Вс'][t.weekday]}</span>
                          <span className="text-sm font-medium">{t.vehicle_name}</span>
                          <span className="text-sm text-gray-500">{t.start_time?.slice(0,5)} — {t.end_time?.slice(0,5)}</span>
                          {t.driver_name && <span className="text-sm text-gray-600">👤 {t.driver_name}</span>}
                        </div>
                        <div className="flex gap-2">
                          <button onClick={() => loadExclusions(t.id)} className="text-blue-500 hover:text-blue-700 text-sm">🚫</button>
                          <button onClick={() => deleteTemplate(t.id)} className="text-red-500 hover:text-red-700 text-sm">🗑️</button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Create new template form */}
              <div>
                <h3 className="text-sm font-semibold text-gray-500 uppercase mb-3">Новый шаблон</h3>
                <div className="grid grid-cols-2 gap-3">
                  <label className="block"><span className="text-xs text-gray-500">Техника (ID)</span>
                    <input type="number" value={templateForm.vehicle_id} onChange={e => setTemplateForm({...templateForm, vehicle_id: e.target.value})}
                      className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" placeholder="ID техники" /></label>
                  <label className="block"><span className="text-xs text-gray-500">Водитель (ID, опционально)</span>
                    <input type="number" value={templateForm.driver_id} onChange={e => setTemplateForm({...templateForm, driver_id: e.target.value})}
                      className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" placeholder="ID водителя" /></label>
                  <label className="block"><span className="text-xs text-gray-500">День недели</span>
                    <select value={templateForm.weekday} onChange={e => setTemplateForm({...templateForm, weekday: Number(e.target.value)})}
                      className="w-full mt-1 px-3 py-2 border rounded-lg text-sm">
                      {['Пн','Вт','Ср','Чт','Пт','Сб','Вс'].map((d, i) => <option key={i} value={i}>{d}</option>)}
                    </select></label>
                  <label className="block"><span className="text-xs text-gray-500">Начало</span>
                    <input type="time" value={templateForm.start_time} onChange={e => setTemplateForm({...templateForm, start_time: e.target.value})}
                      className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" /></label>
                  <label className="block"><span className="text-xs text-gray-500">Окончание</span>
                    <input type="time" value={templateForm.end_time} onChange={e => setTemplateForm({...templateForm, end_time: e.target.value})}
                      className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" /></label>
                </div>
                <button onClick={saveTemplate} disabled={!templateForm.vehicle_id}
                  className="mt-4 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 text-sm font-medium disabled:opacity-50">
                  ➕ Добавить шаблон
                </button>
              </div>

              {/* Exclusions for selected template */}
              {selectedTemplateId && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-500 uppercase mb-3">🚫 Исключения (праздники/отпуска)</h3>
                  <div className="flex gap-2 mb-3">
                    <input type="date" value={exclusionDate} onChange={e => setExclusionDate(e.target.value)}
                      className="px-3 py-2 border rounded-lg text-sm" />
                    <select value={exclusionReason} onChange={e => setExclusionReason(e.target.value)}
                      className="px-3 py-2 border rounded-lg text-sm">
                      <option value="holiday">Праздник</option>
                      <option value="vacation">Отпуск</option>
                      <option value="sick">Больничный</option>
                      <option value="maintenance">ТО</option>
                      <option value="other">Другое</option>
                    </select>
                    <button onClick={addExclusion} disabled={!exclusionDate}
                      className="px-3 py-2 bg-red-600 text-white rounded-lg text-sm disabled:opacity-50">+ Добавить</button>
                  </div>
                  {exclusions.length > 0 && (
                    <div className="space-y-1 max-h-32 overflow-y-auto">
                      {exclusions.map((e: any) => (
                        <div key={e.id} className="flex items-center justify-between p-2 bg-red-50 rounded border border-red-100 text-sm">
                          <span>{e.date} — <span className="text-gray-600">{e.reason === 'holiday' ? 'Праздник' : e.reason === 'vacation' ? 'Отпуск' : e.reason === 'sick' ? 'Больничный' : e.reason === 'maintenance' ? 'ТО' : e.reason}</span></span>
                          <button onClick={() => removeExclusion(e.id)} className="text-red-500 hover:text-red-700">✕</button>
                        </div>
                      ))}
                    </div>
                  )}
                  <p className="text-xs text-gray-400 mt-2">Выберите шаблон выше, чтобы управлять исключениями</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
};

export default ShiftCalendarPage;
