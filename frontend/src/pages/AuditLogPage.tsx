import React, { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import apiClient from '../api/client';

const AuditLogPage: React.FC = () => {
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ action: '', user_id: '' });
  const [pagination, setPagination] = useState({ page: 1, pages: 1, total: 0 });

  const loadLogs = async (page = 1) => {
    try {
      setLoading(true);
      const params: any = { page, per_page: 50 };
      if (filters.action) params.action = filters.action;
      if (filters.user_id) params.user_id = filters.user_id;
      const res = await apiClient.get('/shifts/audit-logs', { params });
      setLogs(res.data.items || []);
      setPagination({ page: res.data.page, pages: res.data.pages, total: res.data.total });
    } catch {} finally { setLoading(false); }
  };

  useEffect(() => { loadLogs(); }, [filters]);

  const actionLabels: Record<string, string> = { login: '🔑 Вход', create: '➕ Создание', update: '✏️ Изменение', delete: '🗑️ Удаление', export: '📥 Экспорт', send: '📤 Отправка' };

  return (
    <Layout>
      <div className="p-6 space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">📋 Журнал действий</h1>

        <div className="bg-white rounded-xl shadow-sm border p-4 flex gap-3 flex-wrap items-end">
          <label className="block"><span className="text-xs text-gray-500">Действие</span>
            <select value={filters.action} onChange={e => setFilters({...filters, action: e.target.value})} className="mt-1 px-3 py-1.5 border rounded-lg text-sm w-40">
              <option value="">Все</option>
              <option value="login">Вход</option><option value="create">Создание</option>
              <option value="update">Изменение</option><option value="delete">Удаление</option>
              <option value="export">Экспорт</option><option value="send">Отправка</option>
            </select></label>
          <label className="block"><span className="text-xs text-gray-500">User ID</span>
            <input type="number" value={filters.user_id} onChange={e => setFilters({...filters, user_id: e.target.value})} className="mt-1 px-3 py-1.5 border rounded-lg text-sm w-24" /></label>
          <button onClick={() => setFilters({ action: '', user_id: '' })} className="px-3 py-1.5 text-gray-500 hover:text-gray-700 text-sm">✕ Сброс</button>
        </div>

        <div className="flex justify-between items-center text-sm text-gray-500">
          <span>Всего: {pagination.total}</span>
          <div className="flex gap-2">
            <button disabled={pagination.page <= 1} onClick={() => loadLogs(pagination.page - 1)} className="px-3 py-1 border rounded disabled:opacity-30">← Назад</button>
            <span className="py-1">{pagination.page} / {pagination.pages}</span>
            <button disabled={pagination.page >= pagination.pages} onClick={() => loadLogs(pagination.page + 1)} className="px-3 py-1 border rounded disabled:opacity-30">Вперёд →</button>
          </div>
        </div>

        {loading ? (
          <div className="flex justify-center py-12"><div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600"></div></div>
        ) : (
          <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Время</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Действие</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Ресурс</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">User ID</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">IP</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Детали</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {logs.map((l: any) => (
                  <tr key={l.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap">{l.created_at ? new Date(l.created_at).toLocaleString('ru-RU') : ''}</td>
                    <td className="px-4 py-3 text-sm"><span className="px-2 py-0.5 bg-gray-100 rounded text-xs font-medium">{actionLabels[l.action] || l.action}</span></td>
                    <td className="px-4 py-3 text-sm text-gray-700">{l.resource_type}{l.resource_id ? ` #${l.resource_id}` : ''}</td>
                    <td className="px-4 py-3 text-sm text-gray-500">{l.user_id || '—'}</td>
                    <td className="px-4 py-3 text-sm text-gray-400 font-mono text-xs">{l.ip_address || '—'}</td>
                    <td className="px-4 py-3 text-sm text-gray-500 max-w-[200px] truncate" title={l.details}>{l.details || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default AuditLogPage;
