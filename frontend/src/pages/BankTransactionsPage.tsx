import React, { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import apiClient from '../api/client';

const BankTransactionsPage: React.FC = () => {
  const [txns, setTxns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ date_from: '', date_to: '', matched: '' });
  const [pagination, setPagination] = useState({ page: 1, pages: 1, total: 0 });
  const [matchModal, setMatchModal] = useState<number | null>(null);
  const [unpaidActs, setUnpaidActs] = useState<any[]>([]);
  const [selectedActId, setSelectedActId] = useState('');

  const loadTxns = async (page = 1) => {
    try {
      setLoading(true);
      const params: any = { page, per_page: 30 };
      if (filters.date_from) params.date_from = filters.date_from;
      if (filters.date_to) params.date_to = filters.date_to;
      if (filters.matched) params.matched = filters.matched;
      const res = await apiClient.get('/shifts/bank/transactions', { params });
      setTxns(res.data.items || []);
      setPagination({ page: res.data.page, pages: res.data.pages, total: res.data.total });
    } catch {} finally { setLoading(false); }
  };

  useEffect(() => { loadTxns(); }, [filters]);

  const openMatchModal = async (txnId: number) => {
    setMatchModal(txnId);
    setSelectedActId('');
    try {
      const res = await apiClient.get('/shifts/acts/unpaid');
      setUnpaidActs(Array.isArray(res.data) ? res.data : []);
    } catch {}
  };

  const matchTxn = async () => {
    if (!matchModal || !selectedActId) return;
    try {
      const res = await apiClient.post(`/shifts/bank/transactions/${matchModal}/match`, { act_id: Number(selectedActId) });
      alert(`✅ ${res.data.message}`);
      setMatchModal(null);
      loadTxns(pagination.page);
    } catch (err: any) { alert('Ошибка: ' + (err.response?.data?.detail || '')); }
  };

  const fmt = (n: number) => n.toLocaleString('ru-RU');

  return (
    <Layout>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">🏦 Банковские транзакции</h1>
          <button onClick={() => {
            const params = new URLSearchParams();
            if (filters.date_from) params.set('date_from', filters.date_from);
            if (filters.date_to) params.set('date_to', filters.date_to);
            if (filters.matched) params.set('matched', filters.matched);
            window.open(`/api/v1/shifts/bank/transactions/export?${params}`, '_blank');
          }} className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 text-sm font-medium">📥 Excel</button>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-xl shadow-sm border p-4 flex gap-3 flex-wrap items-end">
          <label className="block"><span className="text-xs text-gray-500">Дата с</span>
            <input type="date" value={filters.date_from} onChange={e => setFilters({...filters, date_from: e.target.value})} className="mt-1 px-3 py-1.5 border rounded-lg text-sm w-36" /></label>
          <label className="block"><span className="text-xs text-gray-500">Дата по</span>
            <input type="date" value={filters.date_to} onChange={e => setFilters({...filters, date_to: e.target.value})} className="mt-1 px-3 py-1.5 border rounded-lg text-sm w-36" /></label>
          <label className="block"><span className="text-xs text-gray-500">Статус</span>
            <select value={filters.matched} onChange={e => setFilters({...filters, matched: e.target.value})} className="mt-1 px-3 py-1.5 border rounded-lg text-sm w-40">
              <option value="">Все</option><option value="matched">Разнесённые</option><option value="unmatched">Неразнесённые</option>
            </select></label>
          <button onClick={() => setFilters({ date_from: '', date_to: '', matched: '' })} className="px-3 py-1.5 text-gray-500 hover:text-gray-700 text-sm">✕ Сброс</button>
        </div>

        {/* Pagination */}
        <div className="flex justify-between items-center text-sm text-gray-500">
          <span>Всего: {pagination.total}</span>
          <div className="flex gap-2">
            <button disabled={pagination.page <= 1} onClick={() => loadTxns(pagination.page - 1)} className="px-3 py-1 border rounded disabled:opacity-30">← Назад</button>
            <span className="py-1">{pagination.page} / {pagination.pages}</span>
            <button disabled={pagination.page >= pagination.pages} onClick={() => loadTxns(pagination.page + 1)} className="px-3 py-1 border rounded disabled:opacity-30">Вперёд →</button>
          </div>
        </div>

        {/* Table */}
        {loading ? (
          <div className="flex justify-center py-12"><div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600"></div></div>
        ) : (
          <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Дата</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Номер</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Плательщик</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Сумма</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Назначение</th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Акт</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Действия</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {txns.map((t: any) => (
                  <tr key={t.id} className={`hover:bg-gray-50 ${!t.matched_act_id ? 'bg-yellow-50' : ''}`}>
                    <td className="px-4 py-3 text-sm text-gray-600">{t.doc_date}</td>
                    <td className="px-4 py-3 text-sm font-mono text-gray-700">{t.doc_number}</td>
                    <td className="px-4 py-3 text-sm text-gray-900">{t.payer_name || '—'}<br/><span className="text-xs text-gray-400">{t.payer_inn}</span></td>
                    <td className="px-4 py-3 text-sm text-right font-medium text-gray-900">{fmt(t.amount)} ₽</td>
                    <td className="px-4 py-3 text-sm text-gray-500 max-w-[200px] truncate" title={t.purpose}>{t.purpose}</td>
                    <td className="px-4 py-3 text-center">
                      {t.matched_act_number ? (
                        <span className="px-2 py-0.5 bg-green-100 text-green-700 rounded text-xs font-medium">{t.matched_act_number}</span>
                      ) : (
                        <span className="px-2 py-0.5 bg-yellow-100 text-yellow-700 rounded text-xs font-medium">Не разнесено</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {!t.matched_act_id && (
                        <button onClick={() => openMatchModal(t.id)} className="px-2 py-1 bg-indigo-600 text-white rounded text-xs font-medium hover:bg-indigo-700">🔗 Разнести</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Match Modal */}
        {matchModal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-white rounded-xl p-6 w-full max-w-md space-y-4">
              <h2 className="text-lg font-bold text-gray-900">🔗 Разнести на акт</h2>
              <label className="block"><span className="text-xs text-gray-500">Выберите акт</span>
                <select value={selectedActId} onChange={e => setSelectedActId(e.target.value)} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm max-h-40">
                  <option value="">Выберите акт...</option>
                  {unpaidActs.map((a: any) => (
                    <option key={a.id} value={a.id}>{a.act_number} ({a.act_date}) — {fmt(a.outstanding)} ₽ [{a.vehicle_name}]</option>
                  ))}
                </select>
              </label>
              {unpaidActs.length === 0 && <p className="text-xs text-orange-600">Нет неоплаченных актов</p>}
              <div className="flex gap-3 justify-end">
                <button onClick={() => setMatchModal(null)} className="px-4 py-2 text-gray-600 text-sm">Отмена</button>
                <button onClick={matchTxn} disabled={!selectedActId} className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium disabled:opacity-50">🔗 Привязать</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default BankTransactionsPage;
