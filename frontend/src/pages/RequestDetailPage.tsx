import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { requestsApi, type Request } from '../api/requests';
import { financeApi, type Invoice, type Act } from '../api/finance';

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  new: { label: 'Новая', color: 'bg-blue-100 text-blue-800' },
  processing: { label: 'В обработке', color: 'bg-yellow-100 text-yellow-800' },
  assigned: { label: 'Назначена', color: 'bg-indigo-100 text-indigo-800' },
  confirmed: { label: 'Подтверждена', color: 'bg-green-100 text-green-800' },
  released: { label: 'Выпущена', color: 'bg-purple-100 text-purple-800' },
  in_progress: { label: 'В работе', color: 'bg-cyan-100 text-cyan-800' },
  completed: { label: 'Завершена', color: 'bg-emerald-100 text-emerald-800' },
  signed: { label: 'Подписана', color: 'bg-teal-100 text-teal-800' },
  closed: { label: 'Закрыта', color: 'bg-gray-100 text-gray-800' },
  cancelled: { label: 'Отменена', color: 'bg-red-100 text-red-800' },
  disputed: { label: 'Спорная', color: 'bg-orange-100 text-orange-800' },
};

const WORKFLOW: { value: string; label: string }[] = [
  { value: 'new', label: '🔵 Новая' },
  { value: 'processing', label: '🟡 В обработке' },
  { value: 'assigned', label: '🟣 Назначена' },
  { value: 'confirmed', label: '🟢 Подтверждена' },
  { value: 'in_progress', label: '🔷 В работе' },
  { value: 'completed', label: '✅ Завершена' },
  { value: 'cancelled', label: '❌ Отменена' },
];

const formatDateTime = (iso: string | null | undefined) => {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('ru-RU');
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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const canEdit = hasPermission('requests', 'update');

  useEffect(() => {
    if (id) loadData(parseInt(id));
  }, [id]);

  const loadData = async (requestId: number) => {
    try {
      setLoading(true);
      const [reqData, allInvoices, allActs] = await Promise.all([
        requestsApi.getById(requestId),
        financeApi.getInvoices({ limit: 500 }),
        financeApi.getActs({ limit: 500 }),
      ]);

      setRequest(reqData);
      setInvoices(allInvoices.filter((i) => i.request_id === requestId));
      setActs(allActs.filter((a) => a.request_id === requestId));
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
    if (!confirm(`Изменить статус на "${WORKFLOW.find((w) => w.value === newStatus)?.label}"?`)) return;
    try {
      const updated = await requestsApi.update(request.id, { status: newStatus as any });
      setRequest(updated);
    } catch (err: any) {
      alert('Ошибка: ' + (err?.response?.data?.detail || err.message));
    }
  };

  const handleDownloadInvoicePdf = async (inv: Invoice) => {
    try {
      const blob = await financeApi.downloadInvoicePdf(inv.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${inv.document_number}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err: any) {
      alert('Ошибка: ' + (err?.response?.data?.detail || err.message));
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error || !request) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-white rounded-lg shadow p-8 max-w-md text-center">
          <div className="text-5xl mb-4">❌</div>
          <h2 className="text-xl font-bold text-gray-900 mb-2">{error || 'Заявка не найдена'}</h2>
          <button onClick={() => navigate('/requests')} className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
            К списку заявок
          </button>
        </div>
      </div>
    );
  }

  const statusLabel = STATUS_LABELS[request.status] || { label: request.status, color: 'bg-gray-100' };

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center space-x-6">
              <h1 className="text-xl font-bold text-gray-900">🚜 СпецТехника Про</h1>
              <button onClick={() => navigate('/')} className="text-gray-600 hover:text-gray-900">Dashboard</button>
              <button onClick={() => navigate('/requests')} className="text-gray-600 hover:text-gray-900">← К заявкам</button>
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
        <div className="px-4 py-6 sm:px-0">
          {/* Заголовок заявки */}
          <div className="bg-white rounded-lg shadow p-6 mb-6">
            <div className="flex justify-between items-start mb-4">
              <div>
                <h2 className="text-2xl font-bold text-gray-900 mb-2">{request.work_type}</h2>
                <div className="flex items-center space-x-2">
                  <span className={`px-3 py-1 text-sm font-semibold rounded-full ${statusLabel.color}`}>
                    {statusLabel.label}
                  </span>
                  <span className="text-sm text-gray-500">#{request.id}</span>
                </div>
              </div>
              {canEdit && (
                <select
                  value={request.status}
                  onChange={(e) => handleStatusChange(e.target.value)}
                  className="px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                >
                  {WORKFLOW.map((w) => (
                    <option key={w.value} value={w.value}>{w.label}</option>
                  ))}
                </select>
              )}
            </div>

            <dl className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 text-sm">
              <div>
                <dt className="text-gray-500">📍 Адрес</dt>
                <dd className="text-gray-900 font-medium">{request.object_address}</dd>
              </div>
              <div>
                <dt className="text-gray-500">📅 Период</dt>
                <dd className="text-gray-900">
                  {formatDateTime(request.planned_start)} — {formatDateTime(request.planned_end)}
                </dd>
              </div>
              <div>
                <dt className="text-gray-500">⏱️ Смена</dt>
                <dd className="text-gray-900">{request.shift_duration_hours || '—'} ч</dd>
              </div>
              <div>
                <dt className="text-gray-500">💰 Ставка клиента</dt>
                <dd className="text-gray-900 font-semibold">{formatMoney(request.client_rate)} ({request.rate_type})</dd>
              </div>
              <div>
                <dt className="text-gray-500">💵 Ожидаемая сумма</dt>
                <dd className="text-gray-900 font-semibold">{formatMoney(request.estimated_amount)}</dd>
              </div>
              <div>
                <dt className="text-gray-500">📞 Источник</dt>
                <dd className="text-gray-900">{request.source_channel} / {request.priority}</dd>
              </div>
              {request.comment && (
                <div className="md:col-span-2 lg:col-span-3">
                  <dt className="text-gray-500">💬 Комментарий</dt>
                  <dd className="text-gray-900">{request.comment}</dd>
                </div>
              )}
            </dl>
          </div>

          {/* Счета */}
          <div className="bg-white rounded-lg shadow p-6 mb-6">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold text-gray-900">
                💰 Счета ({invoices.length})
              </h3>
              <button
                onClick={() => navigate(`/invoices?new=1&request_id=${request.id}`)}
                className="text-sm bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700"
              >
                + Создать счёт
              </button>
            </div>

            {invoices.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <div className="text-4xl mb-2">💰</div>
                <p>К этой заявке ещё не привязаны счета</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">№</th>
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
                            <span className={`px-2 py-1 text-xs font-semibold rounded-full ${STATUS_LABELS[inv.status]?.color || 'bg-gray-100'}`}>
                              {STATUS_LABELS[inv.status]?.label || inv.status}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-right text-sm space-x-2">
                            <button
                              onClick={() => handleDownloadInvoicePdf(inv)}
                              className="text-purple-600 hover:text-purple-900"
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

          {/* Акты */}
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
                        <td className="px-4 py-3 text-sm text-gray-600">{formatDateTime(act.act_date)}</td>
                        <td className="px-4 py-3 text-sm font-semibold">{formatMoney(act.total_amount)}</td>
                        <td className="px-4 py-3">
                          <span className={`px-2 py-1 text-xs font-semibold rounded-full ${STATUS_LABELS[act.status]?.color || 'bg-gray-100'}`}>
                            {STATUS_LABELS[act.status]?.label || act.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
};

export default RequestDetailPage;
