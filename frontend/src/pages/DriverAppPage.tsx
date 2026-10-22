import React, { useEffect, useState } from 'react';
import apiClient from '../api/client';

const DriverAppPage: React.FC = () => {
  const [shifts, setShifts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'today' | 'week'>('today');
  const [reportModal, setReportModal] = useState<number | null>(null);
  const [reportForm, setReportForm] = useState({ odometer_start: '', odometer_end: '', notes: '' });
  const [reportPhotos, setReportPhotos] = useState<FileList | null>(null);
  const [chatModal, setChatModal] = useState<number | null>(null);
  const [messages, setMessages] = useState<any[]>([]);
  const [chatText, setChatText] = useState('');
  const [fuelModal, setFuelModal] = useState<number | null>(null);
  const [fuelForm, setFuelForm] = useState({ quantity_liters: '', odometer_reading: '', engine_hours: '' });
  const [checklistModal, setChecklistModal] = useState<number | null>(null);
  const [checklistItems, setChecklistItems] = useState<any[]>([]);
  const [checklistNotes, setChecklistNotes] = useState('');

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

  const loadMessages = async (taskId: number) => {
    try {
      const res = await apiClient.get(`/shifts/tasks/${taskId}/messages`);
      setMessages(Array.isArray(res.data) ? res.data : []);
      setChatModal(taskId);
    } catch {}
  };

  const sendMessage = async () => {
    if (!chatModal || !chatText.trim()) return;
    try {
      await apiClient.post(`/shifts/tasks/${chatModal}/messages`, { text: chatText });
      setChatText('');
      loadMessages(chatModal);
    } catch (err: any) { alert('Ошибка: ' + (err.response?.data?.detail || '')); }
  };

  const submitFuel = async () => {
    if (!fuelModal || !fuelForm.quantity_liters) return;
    try {
      const res = await apiClient.post(`/shifts/tasks/${fuelModal}/fuel-entry`, {
        quantity_liters: parseFloat(fuelForm.quantity_liters),
        odometer_reading: fuelForm.odometer_reading ? parseFloat(fuelForm.odometer_reading) : null,
        engine_hours: fuelForm.engine_hours ? parseFloat(fuelForm.engine_hours) : null,
      });
      let msg = `⛽ Топливо записано (${fuelForm.quantity_liters} л)`;
      if (res.data.consumption_per_100km) msg += `\nРасход: ${res.data.consumption_per_100km} л/100км`;
      alert(msg);
      setFuelModal(null);
    } catch (err: any) { alert('Ошибка: ' + (err.response?.data?.detail || '')); }
  };

  const loadChecklist = async (taskId: number) => {
    try {
      const res = await apiClient.get(`/shifts/tasks/${taskId}/pre-shift-checklist`);
      if (res.data.submitted) {
        alert(res.data.has_issues ? '⚠️ Чеклист уже отправлен с замечаниями' : '✅ Чеклист уже отправлен');
        return;
      }
      setChecklistItems(res.data.items || []);
      setChecklistNotes('');
      setChecklistModal(taskId);
    } catch (err: any) { alert('Ошибка: ' + (err.response?.data?.detail || '')); }
  };

  const submitChecklist = async () => {
    if (!checklistModal) return;
    try {
      const res = await apiClient.post(`/shifts/tasks/${checklistModal}/pre-shift-checklist`, {
        items: checklistItems, notes: checklistNotes,
      });
      alert(res.data.message);
      setChecklistModal(null);
      loadShifts();
    } catch (err: any) { alert('Ошибка: ' + (err.response?.data?.detail || '')); }
  };

  const submitReport = async () => {
    if (!reportModal) return;
    try {
      const formData = new FormData();
      if (reportForm.odometer_start) formData.append('odometer_start', reportForm.odometer_start);
      if (reportForm.odometer_end) formData.append('odometer_end', reportForm.odometer_end);
      formData.append('notes', reportForm.notes);
      if (reportPhotos) {
        for (let i = 0; i < Math.min(reportPhotos.length, 5); i++) {
          formData.append('photos', reportPhotos[i]);
        }
      }
      await apiClient.post(`/shifts/tasks/${reportModal}/mobile-report`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      alert('✅ Отчёт отправлен!');
      setReportModal(null);
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
              <div className="flex gap-1 mt-1">
                {(s.status === 'planned' || s.status === 'confirmed') && (
                  <button onClick={() => loadChecklist(s.id)}
                    className="flex-1 py-2 bg-emerald-100 text-emerald-700 rounded-lg text-xs font-medium hover:bg-emerald-200">
                    ✅ Приёмка
                  </button>
                )}
                <button onClick={() => { setFuelModal(s.id); setFuelForm({ quantity_liters: '', odometer_reading: '', engine_hours: '' }); }}
                  className="flex-1 py-2 bg-orange-100 text-orange-700 rounded-lg text-xs font-medium hover:bg-orange-200">
                  ⛽ Топливо
                </button>
                <button onClick={() => loadMessages(s.id)}
                  className="flex-1 py-2 bg-gray-100 text-gray-700 rounded-lg text-xs font-medium hover:bg-gray-200">
                  💬 Чат
                </button>
              </div>
              {s.status === 'completed' && !s.report_id && (
                <button onClick={() => { setReportModal(s.id); setReportForm({ odometer_start: '', odometer_end: '', notes: '' }); setReportPhotos(null); }}
                  className="w-full py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700">
                  📋 Отправить отчёт
                </button>
              )}
              {s.report_id && (
                <div className="text-xs text-green-600 font-medium">✅ Отчёт отправлен</div>
              )}
            </div>
          ))
        )}
      </div>

      {/* Fuel Entry Modal */}
      {fuelModal && (
        <div className="fixed inset-0 bg-black/50 flex items-end z-50">
          <div className="bg-white rounded-t-2xl w-full p-6 space-y-4">
            <div className="flex justify-between items-center">
              <h2 className="text-lg font-bold">⛽ Запись топлива</h2>
              <button onClick={() => setFuelModal(null)} className="text-gray-400 text-xl">✕</button>
            </div>
            <label className="block"><span className="text-xs text-gray-500">Количество (литры)</span>
              <input type="number" step="0.1" value={fuelForm.quantity_liters} onChange={e => setFuelForm({...fuelForm, quantity_liters: e.target.value})}
                className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" placeholder="0.0" /></label>
            <label className="block"><span className="text-xs text-gray-500">Пробег (км, опционально)</span>
              <input type="number" step="0.1" value={fuelForm.odometer_reading} onChange={e => setFuelForm({...fuelForm, odometer_reading: e.target.value})}
                className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" /></label>
            <label className="block"><span className="text-xs text-gray-500">Моточасы (опционально)</span>
              <input type="number" step="0.1" value={fuelForm.engine_hours} onChange={e => setFuelForm({...fuelForm, engine_hours: e.target.value})}
                className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" /></label>
            <button onClick={submitFuel} disabled={!fuelForm.quantity_liters}
              className="w-full py-3 bg-orange-600 text-white rounded-xl text-base font-bold hover:bg-orange-700 disabled:opacity-50">
              ⛽ Записать
            </button>
          </div>
        </div>
      )}

      {/* Pre-Shift Checklist Modal */}
      {checklistModal && (
        <div className="fixed inset-0 bg-black/50 flex items-end z-50">
          <div className="bg-white rounded-t-2xl w-full p-6 max-h-[85vh] overflow-y-auto space-y-4">
            <div className="flex justify-between items-center">
              <h2 className="text-lg font-bold">✅ Приёмка техники</h2>
              <button onClick={() => setChecklistModal(null)} className="text-gray-400 text-xl">✕</button>
            </div>
            <div className="space-y-2">
              {checklistItems.map((item: any, i: number) => (
                <div key={item.key} className={`flex items-center justify-between p-3 rounded-lg border ${item.passed === false ? 'bg-red-50 border-red-200' : 'bg-green-50 border-green-200'}`}>
                  <span className="text-sm font-medium">{item.label} {item.required && <span className="text-red-500">*</span>}</span>
                  <div className="flex gap-2">
                    <button onClick={() => { const updated = [...checklistItems]; updated[i] = {...updated[i], passed: true}; setChecklistItems(updated); }}
                      className={`px-3 py-1 rounded text-xs font-medium ${item.passed !== false ? 'bg-green-600 text-white' : 'bg-gray-200 text-gray-600'}`}>✅ ОК</button>
                    <button onClick={() => { const updated = [...checklistItems]; updated[i] = {...updated[i], passed: false}; setChecklistItems(updated); }}
                      className={`px-3 py-1 rounded text-xs font-medium ${item.passed === false ? 'bg-red-600 text-white' : 'bg-gray-200 text-gray-600'}`}>❌ Проблема</button>
                  </div>
                </div>
              ))}
            </div>
            <label className="block"><span className="text-xs text-gray-500">Заметки</span>
              <textarea value={checklistNotes} onChange={e => setChecklistNotes(e.target.value)}
                className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" rows={2} /></label>
            <button onClick={submitChecklist}
              className="w-full py-3 bg-emerald-600 text-white rounded-xl text-base font-bold hover:bg-emerald-700">
              ✅ Отправить чеклист
            </button>
          </div>
        </div>
      )}

      {/* Chat Modal */}
      {chatModal && (
        <div className="fixed inset-0 bg-black/50 flex items-end z-50">
          <div className="bg-white rounded-t-2xl w-full p-4 max-h-[80vh] flex flex-col">
            <div className="flex justify-between items-center mb-3">
              <h2 className="text-lg font-bold">💬 Чат</h2>
              <button onClick={() => setChatModal(null)} className="text-gray-400 text-xl">✕</button>
            </div>
            <div className="flex-1 overflow-y-auto space-y-2 mb-3 min-h-[200px]">
              {messages.length === 0 ? <p className="text-center text-gray-400 text-sm py-4">Нет сообщений</p> :
                messages.map((m: any) => (
                  <div key={m.id} className={`flex ${m.is_mine ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[80%] px-3 py-2 rounded-xl text-sm ${m.is_mine ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-900'}`}>
                      <p>{m.text}</p>
                      <p className={`text-[10px] mt-1 ${m.is_mine ? 'text-blue-200' : 'text-gray-400'}`}>
                        {m.sent_at ? new Date(m.sent_at).toLocaleTimeString('ru-RU', {hour:'2-digit',minute:'2-digit'}) : ''}
                      </p>
                    </div>
                  </div>
                ))
              }
            </div>
            <div className="flex gap-2">
              <input value={chatText} onChange={e => setChatText(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && sendMessage()}
                placeholder="Сообщение..." className="flex-1 px-3 py-2 border rounded-lg text-sm" />
              <button onClick={sendMessage} disabled={!chatText.trim()}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium disabled:opacity-50">→</button>
            </div>
          </div>
        </div>
      )}

      {/* Report Modal */}
      {reportModal && (
        <div className="fixed inset-0 bg-black/50 flex items-end z-50">
          <div className="bg-white rounded-t-2xl w-full p-6 space-y-4 max-h-[85vh] overflow-y-auto">
            <div className="flex justify-between items-center">
              <h2 className="text-lg font-bold">📋 Отчёт о смене</h2>
              <button onClick={() => setReportModal(null)} className="text-gray-400 text-xl">✕</button>
            </div>
            <label className="block"><span className="text-xs text-gray-500">Пробег начало (км)</span>
              <input type="number" step="0.1" value={reportForm.odometer_start} onChange={e => setReportForm({...reportForm, odometer_start: e.target.value})}
                className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" /></label>
            <label className="block"><span className="text-xs text-gray-500">Пробег конец (км)</span>
              <input type="number" step="0.1" value={reportForm.odometer_end} onChange={e => setReportForm({...reportForm, odometer_end: e.target.value})}
                className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" /></label>
            <label className="block"><span className="text-xs text-gray-500">Заметки</span>
              <textarea value={reportForm.notes} onChange={e => setReportForm({...reportForm, notes: e.target.value})}
                className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" rows={3} /></label>
            <label className="block"><span className="text-xs text-gray-500">Фото (до 5)</span>
              <input type="file" multiple accept="image/*" onChange={e => setReportPhotos(e.target.files)}
                className="w-full mt-1 text-sm" /></label>
            <button onClick={submitReport}
              className="w-full py-3 bg-green-600 text-white rounded-xl text-base font-bold hover:bg-green-700">
              ✅ Отправить отчёт
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default DriverAppPage;
