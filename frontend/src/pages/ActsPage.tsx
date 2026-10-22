import React, { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import apiClient from '../api/client';

const ActsPage: React.FC = () => {
  const [acts, setActs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [counterparties, setCounterparties] = useState<any[]>([]);
  const [sendModal, setSendModal] = useState<number | null>(null);
  const [selectedBoxId, setSelectedBoxId] = useState('');
  const [sending, setSending] = useState(false);
  const [selectedActIds, setSelectedActIds] = useState<Set<number>>(new Set());
  const [bulkModal, setBulkModal] = useState(false);
  const [bulkBoxId, setBulkBoxId] = useState('');
  const [refreshing, setRefreshing] = useState(false);

  const [filters, setFilters] = useState({ date_from: '', date_to: '', status: '', search: '' });
  const [pagination, setPagination] = useState({ page: 1, pages: 1, total: 0 });

  const loadActs = async (page = 1) => {
    try {
      setLoading(true);
      const params: any = { page, per_page: 20 };
      if (filters.date_from) params.date_from = filters.date_from;
      if (filters.date_to) params.date_to = filters.date_to;
      if (filters.status) params.status = filters.status;
      if (filters.search) params.search = filters.search;
      const res = await apiClient.get('/shifts/acts/registry', { params });
      setActs(Array.isArray(res.data.items) ? res.data.items : []);
      setPagination({ page: res.data.page, pages: res.data.pages, total: res.data.total });
    } catch {} finally { setLoading(false); }
  };

  const loadCounterparties = async () => {
    try {
      const res = await apiClient.get('/shifts/diadoc/counterparties');
      setCounterparties(Array.isArray(res.data) ? res.data : []);
    } catch {}
  };

  useEffect(() => { loadActs(); }, [filters]);

  const toggleSelect = (id: number) => {
    const next = new Set(selectedActIds);
    next.has(id) ? next.delete(id) : next.add(id);
    setSelectedActIds(next);
  };

  const selectAllDrafts = () => {
    const drafts = acts.filter(a => a.status === 'draft').map(a => a.id);
    setSelectedActIds(new Set(drafts));
  };

  const signAct = async (actId: number) => {
    if (!confirm('Подписать акт КЭП?')) return;
    try {
      const res = await apiClient.post(`/shifts/acts/${actId}/sign`, { certificate_thumbprint: '' });
      alert(`✅ ${res.data.message}`);
      loadActs(pagination.page);
    } catch (err: any) { alert('Ошибка: ' + (err.response?.data?.detail || '')); }
  };

  const refreshStatuses = async () => {
    setRefreshing(true);
    try {
      const res = await apiClient.post('/shifts/diadoc/refresh-statuses');
      alert(`✅ Обновлено: ${res.data.updated} из ${res.data.total_checked}`);
      loadActs();
    } catch (err: any) { alert('Ошибка: ' + (err.response?.data?.detail || '')); }
    finally { setRefreshing(false); }
  };

  const bulkSend = async () => {
    if (!bulkBoxId || selectedActIds.size === 0) return;
    setSending(true);
    try {
      const res = await apiClient.post('/shifts/diadoc/bulk-send', {
        act_ids: Array.from(selectedActIds), counterparty_box_id: bulkBoxId,
      });
      alert(`📨 Отправлено: ${res.data.sent}, ошибок: ${res.data.errors}`);
      setBulkModal(false);
      setSelectedActIds(new Set());
      loadActs();
    } catch (err: any) { alert('Ошибка: ' + (err.response?.data?.detail || '')); }
    finally { setSending(false); }
  };

  const openSendModal = async (actId: number) => {
    setSendModal(actId);
    setSelectedBoxId('');
    await loadCounterparties();
  };

  const sendAct = async () => {
    if (!sendModal || !selectedBoxId) return;
    setSending(true);
    try {
      const res = await apiClient.post('/shifts/diadoc/send-act', {
        act_id: sendModal, counterparty_box_id: selectedBoxId,
      });
      alert(`✅ ${res.data.message}`);
      setSendModal(null);
      loadActs();
    } catch (err: any) { alert('Ошибка: ' + (err.response?.data?.detail || '')); }
    finally { setSending(false); }
  };

  const statusLabels: Record<string, { label: string; color: string }> = {
    draft: { label: 'Черновик', color: 'bg-gray-100 text-gray-700' },
    sent_to_edo: { label: '📤 Отправлен в ЭДО', color: 'bg-blue-100 text-blue-700' },
    signed: { label: '✅ Подписан', color: 'bg-green-100 text-green-700' },
    rejected: { label: '❌ Отклонён', color: 'bg-red-100 text-red-700' },
  };

  return (
    <Layout>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <h1 className="text-2xl font-bold text-gray-900">📄 Акты выполненных работ</h1>
          <div className="flex gap-2">
            <button onClick={refreshStatuses} disabled={refreshing}
              className="px-3 py-2 bg-blue-100 text-blue-700 rounded-lg text-sm font-medium hover:bg-blue-200 disabled:opacity-50">
              {refreshing ? '⏳' : '🔄'} Обновить статусы
            </button>
            {selectedActIds.size > 0 && (
              <button onClick={() => { setBulkModal(true); setBulkBoxId(''); loadCounterparties(); }}
                className="px-3 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700">
                📨 Отправить выбранные ({selectedActIds.size})
              </button>
            )}
          </div>
        </div>

        {loading ? (
          <div className="flex justify-center py-12"><div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600"></div></div>
        ) : acts.length === 0 ? (
          <p className="text-gray-400 text-center py-8">Нет актов. Создайте через «Генерация актов» на странице утилизации.</p>
        ) : (
          <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Номер</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Дата</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Техника</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Часов</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Сумма</th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Статус</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Действия</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {acts.map((a: any) => {
                  const st = statusLabels[a.status] || statusLabels.draft;
                  return (
                    <tr key={a.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-mono text-gray-700">{a.act_number}</td>
                      <td className="px-4 py-3 text-sm text-gray-600">{a.act_date}</td>
                      <td className="px-4 py-3 text-sm text-gray-900">{a.vehicle_name || a.vehicle_id}</td>
                      <td className="px-4 py-3 text-sm text-right text-gray-600">{a.hours_worked}</td>
                      <td className="px-4 py-3 text-sm text-right font-medium text-gray-900">{(a.total_amount || 0).toLocaleString('ru-RU')} ₽</td>
                      <td className="px-4 py-3 text-center">
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${st.color}`}>{st.label}</span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex gap-1 justify-end">
                        {a.status === 'draft' && (
                          <>
                            <button onClick={() => signAct(a.id)}
                              className="px-2 py-1 bg-emerald-600 text-white rounded text-xs font-medium hover:bg-emerald-700">
                              ✍️ КЭП
                            </button>
                            <button onClick={() => openSendModal(a.id)}
                              className="px-2 py-1 bg-indigo-600 text-white rounded text-xs font-medium hover:bg-indigo-700">
                              📤 Diadoc
                            </button>
                          </>
                        )}
                        {a.status === 'signed' && a.signature && (
                          <span className="text-xs text-green-600" title="Подписан КЭП">✍️</span>
                        )}
                      </div>
                        {a.edo_message_id && (
                          <span className="text-xs text-gray-400 ml-2" title={a.edo_message_id}>ID: {a.edo_message_id.slice(0, 8)}…</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Bulk Send Modal */}
        {bulkModal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-white rounded-xl p-6 w-full max-w-md space-y-4">
              <h2 className="text-lg font-bold text-gray-900">📨 Массовая отправка ({selectedActIds.size} актов)</h2>
              <label className="block">
                <span className="text-xs text-gray-500">Контрагент</span>
                <select value={bulkBoxId} onChange={e => setBulkBoxId(e.target.value)}
                  className="w-full mt-1 px-3 py-2 border rounded-lg text-sm">
                  <option value="">Выберите контрагента...</option>
                  {counterparties.map((c: any) => (
                    <option key={c.box_id} value={c.box_id}>{c.name} (ИНН: {c.inn})</option>
                  ))}
                </select>
              </label>
              <div className="flex gap-3 justify-end">
                <button onClick={() => setBulkModal(false)} className="px-4 py-2 text-gray-600 hover:text-gray-800 text-sm">Отмена</button>
                <button onClick={bulkSend} disabled={!bulkBoxId || sending}
                  className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50">
                  {sending ? '⏳ Отправка...' : `📨 Отправить ${selectedActIds.size} актов`}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Send Modal */}
        {sendModal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-white rounded-xl p-6 w-full max-w-md space-y-4">
              <h2 className="text-lg font-bold text-gray-900">📤 Отправить акт в Diadoc</h2>
              <label className="block">
                <span className="text-xs text-gray-500">Контрагент</span>
                <select value={selectedBoxId} onChange={e => setSelectedBoxId(e.target.value)}
                  className="w-full mt-1 px-3 py-2 border rounded-lg text-sm">
                  <option value="">Выберите контрагента...</option>
                  {counterparties.map((c: any) => (
                    <option key={c.box_id} value={c.box_id}>{c.name} (ИНН: {c.inn})</option>
                  ))}
                </select>
              </label>
              {counterparties.length === 0 && (
                <p className="text-xs text-orange-600">⚠️ Контрагенты не загружены. Проверьте настройки Diadoc.</p>
              )}
              <div className="flex gap-3 justify-end">
                <button onClick={() => setSendModal(null)} className="px-4 py-2 text-gray-600 hover:text-gray-800 text-sm">Отмена</button>
                <button onClick={sendAct} disabled={!selectedBoxId || sending}
                  className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50">
                  {sending ? '⏳ Отправка...' : '📤 Отправить'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default ActsPage;
