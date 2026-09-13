import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { requestsApi, type Request, type StatusLogEntry } from '../api/requests';
import { financeApi, type Invoice, type Act } from '../api/finance';
import { exportApi, downloadBlob } from '../api/export';

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: string }> = {
  new: { label: 'Новая', color: 'bg-blue-100 text-blue-800', icon: '🆕' },
  processing: { label: 'В обработке', color: 'bg-yellow-100 text-yellow-800', icon: '⏳' },
  assigned: { label: 'Назначена', color: 'bg-indigo-100 text-indigo-800', icon: '👤' },
  confirmed: { label: 'Подтверждена', color: 'bg-green-100 text-green-800', icon: '✅' },
  released: { label: 'Выпущена', color: 'bg-purple-100 text-purple-800', icon: '🚀' },
  in_progress: { label: 'В работе', color: 'bg-cyan-100 text-cyan-800', icon: '🔧' },
  completed: { label: 'Завершена', color: 'bg-emerald-100 text-emerald-800', icon: '🏁' },
  signed: { label: 'Подписана', color: 'bg-teal-100 text-teal-800', icon: '✍️' },
  closed: { label: 'Закрыта', color: 'bg-gray-100 text-gray-800', icon: '🔒' },
  cancelled: { label: 'Отменена', color: 'bg-red-100 text-red-800', icon: '❌' },
  disputed: { label: 'Спорная', color: 'bg-orange-100 text-orange-800', icon: '⚠️' },
};

const WORKFLOW: { value: string; label: string; icon: string }[] = [
  { value: 'new', label: 'Новая', icon: '🆕' },
  { value: 'processing', label: 'В обработке', icon: '⏳' },
  { value: 'assigned', label: 'Назначена', icon: '👤' },
  { value: 'confirmed', label: 'Подтверждена', icon: '✅' },
  { value: 'in_progress', label: 'В работе', icon: '🔧' },
  { value: 'completed', label: 'Завершена', icon: '🏁' },
  { value: 'closed', label: 'Закрыта', icon: '🔒' },
  { value: 'cancelled', label: 'Отменена', icon: '❌' },
];

const INVOICE_STATUS_LABELS: Record<string, { label: string; color: string }> = {
  draft: { label: 'Черновик', color: 'bg-gray-100 text-gray-800' },
  sent: { label: 'Отправлен', color: 'bg-blue-100 text-blue-800' },
  paid: { label: 'Оплачен', color: 'bg-green-100 text-green-800' },
  partially_paid: { label: 'Частично', color: 'bg-yellow-100 text-yellow-800' },
  overdue: { label: 'Просрочен', color: 'bg-orange-100 text-orange-800' },
  cancelled: { label: 'Отменён', color: 'bg-red-100 text-red-800' },
};

const formatDateTime = (iso: string | null | undefined) => {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const formatMoney = (v: string | number | null | undefined) => {
  if (v === null || v === undefined || v === '') return '—';
  const num = typeof v === 'string' ? parseFloat(v) : v;
  return `${num.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ₽`;
};

export const RequestDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user, logout, hasPermission } = useAuth();

  const [request, setRequest] = useState<Request | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [acts, setActs] = useState<Act[]>([]);
  const [history, setHistory] = useState<StatusLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [statusUpdating, setStatusUpdating] = useState(false);

  const canEdit = hasPermission('requests', 'update');
  const canCreateInvoice = hasPermission('finance', 'create');

  useEffect(() => {
    if (id) loadData(parseInt(id));
  }, [id]);

  const loadData = async (requestId: number) => {
    try {
      setLoading(true);
      const [reqData, allInvoices, allActs, historyData] = await Promise.allSettled([
        requestsApi.getById(requestId),
        financeApi.getInvoices({ limit: 500 }),
        financeApi.getActs({ limit: 500 }),
        requestsApi.getHistory(requestId),
      ]);

      if (reqData.status === 'fulfilled') {
        setRequest(reqData.value);
      } else {
        setError('Не удалось загрузить заявку');
        return;
      }

      if (allInvoices.status === 'fulfilled') {
        setInvoices(allInvoices.value.filter((i) => i.request_id === requestId));
      }
      if (allActs.status === 'fulfilled') {
        setActs(allActs.value.filter((a) => a.request_id === requestId));
      }
      if (historyData.status === 'fulfilled') {
        setHistory(historyData.value);
      }
      setError('');
    } catch (err: any) {
      console.error('Failed to load request:', err);
      setError('Не удалось загрузить заявку');
    } finally {
      setLoading(false);
    }
  };

  const handleStatusChange = async (newStatus: string) => {
    if (!request) return;
    const config = WORKFLOW.find((w) => w.value === newStatus);
    if (!confirm(`Изменить статус на "${config?.icon} ${config?.label}"?`)) {
      window.location.reload();
      return;
    }
    try {
      setStatusUpdating(true);
      const updated = await requestsApi.update(request.id, { status: newStatus as any });
      setRequest(updated);
      // Перезагружаем историю после смены статуса
      const historyData = await requestsApi.getHistory(request.id);
      setHistory(historyData);
    } catch (err: any) {
      alert('Ошибка: ' + (err?.response?.data?.detail || err.message));
      window.location.reload();
    } finally {
      setStatusUpdating(false);
    }
  };

  const handleDownloadInvoicePdf = async (inv: Invoice) => {
    try {
      const blob = await financeApi.downloadInvoicePdf(inv.id);
      downloadBlob(blob, `${inv.document_number || `invoice-${inv.id}`}.pdf`);
    } catch (err: any) {
      alert('Ошибка: ' + (err?.response?.data?.detail || err.message));
    }
  };

  const handleCreateInvoice = () => {
    navigate(`/invoices?new=1&request_id=${request?.id}`);
  };

  const handleExportReport = async () => {
    if (!request) return;
    try {
      const blob = await exportApi.requestReport(request.id);
      downloadBlob(blob, `request_${request.id}_report.pdf`);
    } catch (err: any) {
      alert('Ошибка экспорта: ' + (err?.response?.data?.detail || err.message));
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Загрузка заявки...</p>
        </div>
      </div>
    );
  }

  if (error || !request) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-white rounded-lg shadow p-8 max-w-md text-center">
          <div className="text-5xl mb-4">❌</div>
          <h2 className="text-xl font-bold text-gray-900 mb-2">{error || 'Заявка не найдена'}</h2>
          <button
            onClick={() => navigate('/requests')}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            ← К списку заявок
          </button>
        </div>
      </div>
    );
  }

  const statusConfig = STATUS_CONFIG[request.status] || { label: request.status, color: 'bg-gray-100', icon: '📋' };

  const invoicesTotal = invoices.reduce((sum, i) => sum + parseFloat(i.total || '0'), 0);
  const invoicesPaid = invoices.reduce((sum, i) => sum + parseFloat(i.paid_amount || '0'), 0);
  const invoicesProgress = invoicesTotal > 0 ? (invoicesPaid / invoicesTotal) * 100 : 0;

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center space-x-6">
              <h1 className="text-xl font-bold text-gray-900">🚜 СпецТехника Про</h1>
              <button onClick={() => navigate('/')} className="text-gray-600 hover:text-gray-900">Dashboard</button>
              <button onClick={() => navigate('/requests')} className="text-gray-600 hover:text-gray-900">
                ← К заявкам
              </button>
              <span className="text-blue-600 font-medium">Заявка #{request.id}</span>
            </div>
            <div className="flex items-center space-x-4">
              <span className="text-gray-700">{user?.email}</span>
              <button
                onClick={() => { logout(); navigate('/login'); }}
                className="bg-red-600 text-white px-4 py-2 rounded hover:bg-red-700"
              >
                Выйти
              </button>
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0 space-y-6">
          {/* === ШАПКА ЗАЯВКИ === */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex flex-col md:flex-row md:justify-between md:items-start gap-4 mb-6">
              <div>
                <div className="flex items-center space-x-3 mb-2">
                  <span className="text-4xl">{statusConfig.icon}</span>
                  <div>
                    <h2 className="text-2xl font-bold text-gray-900">{request.work_type}</h2>
                    <div className="flex items-center space-x-2 mt-1">
                      <span className={`px-3 py-1 text-sm font-semibold rounded-full ${statusConfig.color}`}>
                        {statusConfig.label}
                      </span>
                      <span className="text-sm text-gray-500">#{request.id}</span>
                    </div>
                  </div>
                </div>
              </div>
              {canEdit && (
                <div className="flex items-center space-x-2 flex-wrap gap-2">
                  <button
                    onClick={handleExportReport}
                    className="px-3 py-2 bg-green-600 text-white rounded hover:bg-green-700 text-sm"
                    title="Скачать PDF-отчёт по заявке"
                  >
                    📥 PDF-отчёт
                  </button>
                  <label className="text-sm text-gray-600">Статус:</label>
                  <select
                    value={request.status}
                    onChange={(e) => handleStatusChange(e.target.value)}
                    disabled={statusUpdating}
                    className="px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none disabled:opacity-50"
                  >
                    {WORKFLOW.map((w) => (
                      <option key={w.value} value={w.value}>
                        {w.icon} {w.label}
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>

            <dl className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 text-sm">
              <div className="bg-gray-50 p-3 rounded">
                <dt className="text-gray-500 text-xs uppercase font-semibold mb-1">📍 Адрес объекта</dt>
                <dd className="text-gray-900 font-medium">{request.object_address}</dd>
              </div>
              <div className="bg-gray-50 p-3 rounded">
                <dt className="text-gray-500 text-xs uppercase font-semibold mb-1">📅 Период выполнения</dt>
                <dd className="text-gray-900">
                  {formatDateTime(request.planned_start)}
                  <br />
                  {formatDateTime(request.planned_end)}
                </dd>
              </div>
              <div className="bg-gray-50 p-3 rounded">
                <dt className="text-gray-500 text-xs uppercase font-semibold mb-1">⏱️ Тип / Смена</dt>
                <dd className="text-gray-900">
                  {(request as any).request_type || 'one_time'} / {request.shift_duration_hours || '—'} ч
                </dd>
              </div>
              <div className="bg-gray-50 p-3 rounded">
                <dt className="text-gray-500 text-xs uppercase font-semibold mb-1">💰 Ставка клиента</dt>
                <dd className="text-gray-900 font-semibold">
                  {formatMoney(request.client_rate)} ({request.rate_type})
                </dd>
              </div>
              <div className="bg-gray-50 p-3 rounded">
                <dt className="text-gray-500 text-xs uppercase font-semibold mb-1">💵 Ожидаемая сумма</dt>
                <dd className="text-gray-900 font-semibold text-green-700">
                  {formatMoney(request.estimated_amount)}
                </dd>
              </div>
              <div className="bg-gray-50 p-3 rounded">
                <dt className="text-gray-500 text-xs uppercase font-semibold mb-1">🎯 Приоритет / Источник</dt>
                <dd className="text-gray-900">{request.priority} / {request.source_channel}</dd>
              </div>
              {request.comment && (
                <div className="bg-gray-50 p-3 rounded md:col-span-2 lg:col-span-3">
                  <dt className="text-gray-500 text-xs uppercase font-semibold mb-1">💬 Комментарий</dt>
                  <dd className="text-gray-900">{request.comment}</dd>
                </div>
              )}
            </dl>
          </div>

          {/* === СЧЕТА === */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-3 mb-4">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">
                  💰 Счета ({invoices.length})
                </h3>
                {invoices.length > 0 && (
                  <div className="mt-2">
                    <div className="flex items-center space-x-3 text-sm">
                      <div className="flex-1 bg-gray-200 rounded-full h-2 max-w-xs">
                        <div
                          className={`h-2 rounded-full ${invoicesProgress === 100 ? 'bg-green-500' : 'bg-blue-500'}`}
                          style={{ width: `${invoicesProgress}%` }}
                        ></div>
                      </div>
                      <span className="text-gray-600">
                        Оплачено {formatMoney(invoicesPaid)} из {formatMoney(invoicesTotal)} ({invoicesProgress.toFixed(0)}%)
                      </span>
                    </div>
                  </div>
                )}
              </div>
              {canCreateInvoice && (
                <button
                  onClick={handleCreateInvoice}
                  className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 text-sm"
                >
                  + Создать счёт
                </button>
              )}
            </div>

            {invoices.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                <div className="text-5xl mb-3">💰</div>
                <p>К этой заявке ещё не привязаны счета</p>
                {canCreateInvoice && (
                  <button
                    onClick={handleCreateInvoice}
                    className="mt-4 text-blue-600 hover:text-blue-900 text-sm font-medium"
                  >
                    + Создать первый счёт
                  </button>
                )}
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">№</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Дата</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Срок</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Сумма</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Оплачено</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Статус</th>
                      <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Действия</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {invoices.map((inv) => {
                      const paid = parseFloat(inv.paid_amount || '0');
                      const total = parseFloat(inv.total || '0');
                      const progress = total > 0 ? (paid / total) * 100 : 0;

                      return (
                        <tr key={inv.id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm font-mono text-gray-900">{inv.document_number}</td>
                          <td className="px-4 py-3 text-sm text-gray-600">
                            {inv.invoice_date ? new Date(inv.invoice_date).toLocaleDateString('ru-RU') : '—'}
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-600">
                            {inv.due_date ? new Date(inv.due_date).toLocaleDateString('ru-RU') : '—'}
                          </td>
                          <td className="px-4 py-3 text-sm font-semibold">{formatMoney(inv.total)}</td>
                          <td className="px-4 py-3 text-sm">
                            <div className="flex items-center space-x-2">
                              <div className="w-20 bg-gray-200 rounded-full h-2">
                                <div
                                  className={`h-2 rounded-full ${progress === 100 ? 'bg-green-500' : 'bg-blue-500'}`}
                                  style={{ width: `${progress}%` }}
                                ></div>
                              </div>
                              <span className="text-xs text-gray-600">{formatMoney(inv.paid_amount)}</span>
                            </div>
                          </td>
                          <td className="px-4 py-3">
                            <span className={`px-2 py-1 text-xs font-semibold rounded-full ${INVOICE_STATUS_LABELS[inv.status]?.color || 'bg-gray-100'}`}>
                              {INVOICE_STATUS_LABELS[inv.status]?.label || inv.status}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-right text-sm">
                            <button
                              onClick={() => handleDownloadInvoicePdf(inv)}
                              className="text-purple-600 hover:text-purple-900"
                              title="Скачать PDF"
                            >
                              📄 PDF
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* === АКТЫ === */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold text-gray-900">
                📄 Акты ({acts.length})
              </h3>
              <button
                className="text-sm bg-gray-400 text-white px-3 py-1 rounded cursor-not-allowed"
                disabled
                title="В разработке"
              >
                + Создать акт (скоро)
              </button>
            </div>

            {acts.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <div className="text-4xl mb-2">📄</div>
                <p>К этой заявке ещё не привязаны акты</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">№</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Дата</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Сумма</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Статус</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {acts.map((act) => (
                      <tr key={act.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm font-mono text-gray-900">{act.document_number}</td>
                        <td className="px-4 py-3 text-sm text-gray-600">
                          {act.act_date ? new Date(act.act_date).toLocaleDateString('ru-RU') : '—'}
                        </td>
                        <td className="px-4 py-3 text-sm font-semibold">{formatMoney(act.total_amount)}</td>
                        <td className="px-4 py-3">
                          <span className={`px-2 py-1 text-xs font-semibold rounded-full ${INVOICE_STATUS_LABELS[act.status]?.color || 'bg-gray-100'}`}>
                            {INVOICE_STATUS_LABELS[act.status]?.label || act.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* === ИСТОРИЯ СТАТУСОВ === */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              📜 История изменений ({history.length})
            </h3>

            {history.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <div className="text-4xl mb-2">📜</div>
                <p>История изменений пуста</p>
              </div>
            ) : (
              <div className="relative">
                <div className="absolute left-6 top-0 bottom-0 w-0.5 bg-gray-200"></div>

                <div className="space-y-4">
                  {history.map((entry, idx) => {
                    const toConfig = STATUS_CONFIG[entry.to_status] || { label: entry.to_status, color: 'bg-gray-100', icon: '📋' };
                    const fromConfig = entry.from_status ? (STATUS_CONFIG[entry.from_status] || { label: entry.from_status, color: 'bg-gray-100', icon: '📋' }) : null;
                    const isLast = idx === history.length - 1;

                    return (
                      <div key={entry.id} className="relative flex items-start gap-4 pl-14">
                        <div className={`absolute left-4 top-2 w-5 h-5 rounded-full border-4 border-white flex items-center justify-center text-xs ${
                          isLast ? 'bg-blue-500' : 'bg-gray-400'
                        }`}>
                          <span className="text-white text-[10px]">{toConfig.icon}</span>
                        </div>

                        <div className={`flex-1 ${isLast ? 'bg-blue-50 border-2 border-blue-200' : 'bg-gray-50'} rounded-lg p-4`}>
                          <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                            <div className="flex items-center gap-2 flex-wrap">
                              {fromConfig && (
                                <>
                                  <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${fromConfig.color}`}>
                                    {fromConfig.icon} {fromConfig.label}
                                  </span>
                                  <span className="text-gray-400">→</span>
                                </>
                              )}
                              <span className={`px-2 py-0.5 text-xs font-semibold rounded-full ${toConfig.color}`}>
                                {toConfig.icon} {toConfig.label}
                              </span>
                            </div>
                            <span className="text-xs text-gray-500">
                              {entry.changed_at ? new Date(entry.changed_at).toLocaleString('ru-RU') : '—'}
                            </span>
                          </div>

                          <div className="flex items-center justify-between text-sm">
                            <span className="text-gray-700">
                              👤 <span className="font-medium">{entry.changed_by_email}</span>
                            </span>
                            {entry.comment && (
                              <span className="text-gray-500 italic text-xs ml-2">"{entry.comment}"</span>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
};

export default RequestDetailPage;
