import React, { useEffect, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { emailApi, type EmailLog } from '../api/email';
import { TableSkeleton } from '../components/Skeleton';
import Layout from '../components/Layout';

const STATUS_LABELS: Record<string, { label: string; color: string; icon: string }> = {
  pending: { label: 'В очереди', color: 'bg-yellow-100 text-yellow-800', icon: '⏳' },
  sent: { label: 'Отправлено', color: 'bg-green-100 text-green-800', icon: '✅' },
  delivered: { label: 'Доставлено', color: 'bg-blue-100 text-blue-800', icon: '📬' },
  failed: { label: 'Ошибка', color: 'bg-red-100 text-red-800', icon: '❌' },
  bounced: { label: 'Отклонено', color: 'bg-orange-100 text-orange-800', icon: '🚫' },
};

const formatDateTime = (iso: string | null) => {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

export const EmailLogsPage: React.FC = () => {
  const { hasPermission } = useAuth();
  const [logs, setLogs] = useState<EmailLog[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [viewingLog, setViewingLog] = useState<EmailLog | null>(null);
  const [viewingHtml, setViewingHtml] = useState<string>('');
  const [viewingLoading, setViewingLoading] = useState(false);

  const canView = hasPermission('email_logs', 'view');

  const loadLogs = async () => {
    try {
      setLoading(true);
      const params: any = { limit: 100, offset: 0 };
      if (filterStatus !== 'all') {
        params.status = filterStatus;
      }
      const response = await emailApi.getLogs(params);
      setLogs(response.items);
      setTotal(response.total);
      setError('');
    } catch (err: any) {
      console.error('Failed to load email logs:', err);
      setError('Не удалось загрузить историю email');
    } finally {
      setLoading(false);
    }
  };

  const handleViewLog = async (log: EmailLog) => {
    try {
      setViewingLoading(true);
      const detail = await emailApi.getLogDetail(log.id);
      setViewingLog(log);
      setViewingHtml(detail.html_body || '<p>HTML-версия недоступна</p>');
    } catch (err: any) {
      console.error('Failed to load log detail:', err);
      alert('Ошибка: ' + (err?.response?.data?.detail || err.message));
    } finally {
      setViewingLoading(false);
    }
  };

  const closeModal = () => {
    setViewingLog(null);
    setViewingHtml('');
  };

  useEffect(() => {
    if (canView) {
      loadLogs();
    }
  }, [canView, filterStatus]);

  if (!canView) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-white rounded-lg shadow p-8 max-w-md text-center">
          <div className="text-5xl mb-4">🔒</div>
          <h2 className="text-xl font-bold text-gray-900 mb-2">Доступ запрещён</h2>
          <p className="text-gray-600">У вас нет прав на просмотр истории email</p>
        </div>
      </div>
    );
  }

  return (
    <Layout>
      <div className="px-4 py-6 sm:px-0">
        {/* ===== Заголовок и фильтры ===== */}
        <div className="flex justify-between items-center mb-6">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">📧 История email-отправок</h2>
            <p className="text-sm text-gray-600 mt-1">
              Всего отправлено: <strong>{total}</strong> писем
            </p>
          </div>
          <div className="flex gap-2">
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
            >
              <option value="all">Все статусы</option>
              {Object.entries(STATUS_LABELS).map(([key, { label, icon }]) => (
                <option key={key} value={key}>
                  {icon} {label}
                </option>
              ))}
            </select>
            <button
              onClick={loadLogs}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
            >
              🔄 Обновить
            </button>
          </div>
        </div>

        {/* ===== Ошибка ===== */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-6">
            {error}
          </div>
        )}

        {/* ===== Контент: загрузка / пусто / таблица ===== */}
        {loading ? (
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <TableSkeleton rows={10} columns={6} />
          </div>
        ) : logs.length === 0 ? (
          <div className="bg-white rounded-lg shadow p-12 text-center text-gray-500">
            <div className="text-5xl mb-4">📭</div>
            <p className="text-lg">Email-отправок пока нет</p>
            <p className="text-sm mt-2">
              Письма будут появляться здесь после создания счетов и актов
            </p>
          </div>
        ) : (
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <div className="overflow-x-auto overflow-y-auto max-h-[70vh] border border-gray-200 rounded">
            <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50 sticky top-0 z-10 shadow-sm">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Получатель</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Тема</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Статус</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Отправлено</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Документ</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Действия</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {logs.map((log) => {
                    const statusConfig = STATUS_LABELS[log.status] || {
                      label: log.status,
                      color: 'bg-gray-100',
                      icon: '📧',
                    };
                    return (
                      <tr key={log.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm font-mono text-gray-900">#{log.id}</td>
                        <td className="px-4 py-3 text-sm text-gray-900">
                          <div className="font-medium">{log.to_email}</div>
                          {log.to_name && (
                            <div className="text-xs text-gray-500">{log.to_name}</div>
                          )}
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-700 max-w-md truncate">
                          {log.subject}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap">
                          <span className={`px-2 py-1 text-xs font-semibold rounded-full ${statusConfig.color}`}>
                            {statusConfig.icon} {statusConfig.label}
                          </span>
                          {log.error_message && (
                            <div className="text-xs text-red-600 mt-1 max-w-xs truncate" title={log.error_message}>
                              {log.error_message}
                            </div>
                          )}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-600">
                          {formatDateTime(log.sent_at)}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm">
                          {log.invoice_id && (
                            <span className="px-2 py-1 bg-blue-50 text-blue-700 rounded text-xs">
                              📄 Счёт #{log.invoice_id}
                            </span>
                          )}
                          {log.act_id && (
                            <span className="px-2 py-1 bg-green-50 text-green-700 rounded text-xs">
                              📋 Акт #{log.act_id}
                            </span>
                          )}
                          {!log.invoice_id && !log.act_id && (
                            <span className="text-gray-400 text-xs">—</span>
                          )}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm text-right">
                          <button
                            onClick={() => handleViewLog(log)}
                            disabled={viewingLoading}
                            className="text-blue-600 hover:text-blue-900 disabled:opacity-50"
                            title="Просмотреть письмо"
                          >
                            👁️
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ===== МОДАЛКА ПРОСМОТРА ПИСЬМА (ИСПРАВЛЕНО) ===== */}
        {viewingLog && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl h-[90vh] flex flex-col">
              {/* Шапка модалки */}
              <div className="flex justify-between items-start p-6 border-b">
                <div className="flex-1 pr-4">
                  <h3 className="text-xl font-bold text-gray-900 mb-2">
                    {viewingLog.subject}
                  </h3>
                  <div className="text-sm text-gray-600 space-y-1">
                    <div>
                      <strong>Кому:</strong> {viewingLog.to_email}
                      {viewingLog.to_name && ` (${viewingLog.to_name})`}
                    </div>
                    <div>
                      <strong>Отправлено:</strong> {formatDateTime(viewingLog.sent_at)}
                    </div>
                    <div>
                      <strong>Статус:</strong>{' '}
                      {STATUS_LABELS[viewingLog.status]?.label || viewingLog.status}
                    </div>
                  </div>
                </div>
                <button
                  onClick={closeModal}
                  className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
                  aria-label="Закрыть"
                >
                  ×
                </button>
              </div>

              {/* Содержимое письма */}
              <div className="flex-1 overflow-auto p-6 bg-gray-50">
                <div
                  className="bg-white p-6 rounded shadow"
                  dangerouslySetInnerHTML={{ __html: viewingHtml }}
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default EmailLogsPage;
