import React, { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import apiClient from '../api/client';
import { showToast } from '../utils/toast';

interface SyncLogEntry {
  id: number;
  provider_name: string;
  sync_type: string;
  status: string;
  points_received: number;
  duration_ms: number | null;
  error_message: string | null;
  created_at: string;
  vehicle_id: number | null;
  company_id: number | null;
}

interface SyncStats {
  total_syncs: number;
  success_count: number;
  error_count: number;
  avg_duration_ms: number;
  by_provider: Record<string, { total: number; success: number; error: number }>;
}

const STATUS_COLORS: Record<string, string> = {
  success: '#10b981',
  error: '#ef4444',
  partial: '#f59e0b',
};

const formatDate = (iso: string) => new Date(iso).toLocaleString('ru-RU');

export const SyncLogsPage: React.FC = () => {
  const [logs, setLogs] = useState<SyncLogEntry[]>([]);
  const [stats, setStats] = useState<SyncStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const pageSize = 50;

  // Filters
  const [filterProvider, setFilterProvider] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterDateFrom, setFilterDateFrom] = useState('');
  const [filterDateTo, setFilterDateTo] = useState('');

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = { page, per_page: pageSize };
      if (filterProvider) params.provider = filterProvider;
      if (filterStatus) params.status = filterStatus;
      if (filterDateFrom) params.date_from = filterDateFrom;
      if (filterDateTo) params.date_to = filterDateTo;

      const res = await apiClient.get('/telematics/sync-logs', { params });
      setLogs(res.data.items || res.data);
      setTotal(res.data.total || (res.data.items || res.data).length);
    } catch (err: any) {
      showToast('Ошибка загрузки логов синхронизации', 'error');
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const params: Record<string, any> = {};
      if (filterProvider) params.provider = filterProvider;
      if (filterDateFrom) params.date_from = filterDateFrom;
      if (filterDateTo) params.date_to = filterDateTo;

      const res = await apiClient.get('/telematics/sync-logs/stats', { params });
      setStats(res.data);
    } catch {
      // Stats endpoint may not be ready yet
    }
  };

  useEffect(() => {
    fetchLogs();
    fetchStats();
  }, [page, filterProvider, filterStatus, filterDateFrom, filterDateTo]);

  const totalPages = Math.ceil(total / pageSize);

  return (
    <Layout>
      <div style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 700, marginBottom: '24px', color: '#1e3a5f' }}>
          📡 Логи синхронизации GPS
        </h1>

        {/* Stats Cards */}
        {stats && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '24px' }}>
            <div style={{ background: '#fff', borderRadius: '8px', padding: '16px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
              <div style={{ fontSize: '12px', color: '#6b7280', textTransform: 'uppercase' }}>Всего синхронизаций</div>
              <div style={{ fontSize: '28px', fontWeight: 700, color: '#1e3a5f' }}>{stats.total_syncs}</div>
            </div>
            <div style={{ background: '#fff', borderRadius: '8px', padding: '16px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
              <div style={{ fontSize: '12px', color: '#6b7280', textTransform: 'uppercase' }}>Успешных</div>
              <div style={{ fontSize: '28px', fontWeight: 700, color: '#10b981' }}>{stats.success_count}</div>
            </div>
            <div style={{ background: '#fff', borderRadius: '8px', padding: '16px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
              <div style={{ fontSize: '12px', color: '#6b7280', textTransform: 'uppercase' }}>Ошибок</div>
              <div style={{ fontSize: '28px', fontWeight: 700, color: '#ef4444' }}>{stats.error_count}</div>
            </div>
            <div style={{ background: '#fff', borderRadius: '8px', padding: '16px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
              <div style={{ fontSize: '12px', color: '#6b7280', textTransform: 'uppercase' }}>Среднее время</div>
              <div style={{ fontSize: '28px', fontWeight: 700, color: '#3b82f6' }}>{stats.avg_duration_ms} мс</div>
            </div>
          </div>
        )}

        {/* Filters */}
        <div style={{ display: 'flex', gap: '12px', marginBottom: '16px', flexWrap: 'wrap', alignItems: 'center' }}>
          <select
            value={filterProvider}
            onChange={(e) => { setFilterProvider(e.target.value); setPage(1); }}
            style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid #d1d5db', fontSize: '14px' }}
          >
            <option value="">Все провайдеры</option>
            <option value="wialon">Wialon</option>
            <option value="mapix">Mapix</option>
            <option value="gdemoi">GdeMoi</option>
            <option value="gps_trace">GPS-Trace</option>
            <option value="manual">Manual</option>
          </select>

          <select
            value={filterStatus}
            onChange={(e) => { setFilterStatus(e.target.value); setPage(1); }}
            style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid #d1d5db', fontSize: '14px' }}
          >
            <option value="">Все статусы</option>
            <option value="success">Успех</option>
            <option value="error">Ошибка</option>
          </select>

          <input
            type="date"
            value={filterDateFrom}
            onChange={(e) => { setFilterDateFrom(e.target.value); setPage(1); }}
            placeholder="С"
            style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid #d1d5db', fontSize: '14px' }}
          />
          <input
            type="date"
            value={filterDateTo}
            onChange={(e) => { setFilterDateTo(e.target.value); setPage(1); }}
            placeholder="По"
            style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid #d1d5db', fontSize: '14px' }}
          />

          <button
            onClick={() => { setFilterProvider(''); setFilterStatus(''); setFilterDateFrom(''); setFilterDateTo(''); setPage(1); }}
            style={{ padding: '8px 16px', borderRadius: '6px', border: 'none', background: '#6b7280', color: '#fff', cursor: 'pointer', fontSize: '14px' }}
          >
            Сбросить
          </button>
        </div>

        {/* Table */}
        <div style={{ background: '#fff', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
            <thead>
              <tr style={{ background: '#f9fafb', borderBottom: '1px solid #e5e7eb' }}>
                <th style={{ padding: '12px 16px', textAlign: 'left', fontWeight: 600, color: '#374151' }}>Время</th>
                <th style={{ padding: '12px 16px', textAlign: 'left', fontWeight: 600, color: '#374151' }}>Провайдер</th>
                <th style={{ padding: '12px 16px', textAlign: 'left', fontWeight: 600, color: '#374151' }}>Тип</th>
                <th style={{ padding: '12px 16px', textAlign: 'center', fontWeight: 600, color: '#374151' }}>Статус</th>
                <th style={{ padding: '12px 16px', textAlign: 'right', fontWeight: 600, color: '#374151' }}>Точки</th>
                <th style={{ padding: '12px 16px', textAlign: 'right', fontWeight: 600, color: '#374151' }}>Время (мс)</th>
                <th style={{ padding: '12px 16px', textAlign: 'left', fontWeight: 600, color: '#374151' }}>Ошибка</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={7} style={{ padding: '24px', textAlign: 'center', color: '#6b7280' }}>Загрузка...</td></tr>
              ) : logs.length === 0 ? (
                <tr><td colSpan={7} style={{ padding: '24px', textAlign: 'center', color: '#6b7280' }}>Нет записей</td></tr>
              ) : (
                logs.map((log) => (
                  <tr key={log.id} style={{ borderBottom: '1px solid #f3f4f6' }}>
                    <td style={{ padding: '10px 16px', whiteSpace: 'nowrap' }}>{formatDate(log.created_at)}</td>
                    <td style={{ padding: '10px 16px', fontWeight: 500 }}>{log.provider_name}</td>
                    <td style={{ padding: '10px 16px' }}>{log.sync_type}</td>
                    <td style={{ padding: '10px 16px', textAlign: 'center' }}>
                      <span style={{
                        display: 'inline-block', padding: '2px 8px', borderRadius: '12px', fontSize: '11px', fontWeight: 600,
                        background: `${STATUS_COLORS[log.status] || '#6b7280'}20`,
                        color: STATUS_COLORS[log.status] || '#6b7280',
                      }}>
                        {log.status === 'success' ? '✓ Успех' : '✗ Ошибка'}
                      </span>
                    </td>
                    <td style={{ padding: '10px 16px', textAlign: 'right' }}>{log.points_received}</td>
                    <td style={{ padding: '10px 16px', textAlign: 'right' }}>{log.duration_ms ?? '—'}</td>
                    <td style={{ padding: '10px 16px', maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: '#ef4444', fontSize: '12px' }}>
                      {log.error_message || '—'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div style={{ display: 'flex', justifyContent: 'center', gap: '8px', marginTop: '16px' }}>
            <button
              disabled={page <= 1}
              onClick={() => setPage(p => p - 1)}
              style={{ padding: '8px 16px', borderRadius: '6px', border: '1px solid #d1d5db', background: page <= 1 ? '#f3f4f6' : '#fff', cursor: page <= 1 ? 'not-allowed' : 'pointer' }}
            >
              ← Назад
            </button>
            <span style={{ padding: '8px 16px', fontSize: '14px', color: '#374151' }}>
              Стр. {page} из {totalPages} ({total} записей)
            </span>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage(p => p + 1)}
              style={{ padding: '8px 16px', borderRadius: '6px', border: '1px solid #d1d5db', background: page >= totalPages ? '#f3f4f6' : '#fff', cursor: page >= totalPages ? 'not-allowed' : 'pointer' }}
            >
              Вперёд →
            </button>
          </div>
        )}
      </div>
    </Layout>
  );
};
