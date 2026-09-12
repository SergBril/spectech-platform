import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { financeApi, type Invoice, type Act, type Payout, type PaymentsDashboard } from '../api/finance';

const INVOICE_STATUS_LABELS: Record<string, { label: string; color: string }> = {
  draft: { label: 'Черновик', color: 'bg-gray-100 text-gray-800' },
  sent: { label: 'Отправлен', color: 'bg-blue-100 text-blue-800' },
  paid: { label: 'Оплачен', color: 'bg-green-100 text-green-800' },
  partially_paid: { label: 'Частично', color: 'bg-yellow-100 text-yellow-800' },
  overdue: { label: 'Просрочен', color: 'bg-orange-100 text-orange-800' },
  cancelled: { label: 'Отменён', color: 'bg-red-100 text-red-800' },
};

const ACT_STATUS_LABELS: Record<string, { label: string; color: string }> = {
  draft: { label: 'Черновик', color: 'bg-gray-100 text-gray-800' },
  sent: { label: 'Отправлен', color: 'bg-blue-100 text-blue-800' },
  paid: { label: 'Подписан', color: 'bg-green-100 text-green-800' },
  overdue: { label: 'Просрочен', color: 'bg-orange-100 text-orange-800' },
  cancelled: { label: 'Отменён', color: 'bg-red-100 text-red-800' },
};

const PAYOUT_STATUS_LABELS: Record<string, { label: string; color: string }> = {
  draft: { label: 'Черновик', color: 'bg-gray-100 text-gray-800' },
  sent: { label: 'Одобрен', color: 'bg-blue-100 text-blue-800' },
  paid: { label: 'Выплачен', color: 'bg-green-100 text-green-800' },
  overdue: { label: 'Просрочен', color: 'bg-orange-100 text-orange-800' },
  cancelled: { label: 'Отклонён', color: 'bg-red-100 text-red-800' },
};

const formatDate = (dateStr: string) => {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleDateString('ru-RU');
};

const formatMoney = (v: string | number | null | undefined) => {
  if (v === null || v === undefined || v === '') return '—';
  const num = typeof v === 'string' ? parseFloat(v) : v;
  return `${num.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ₽`;
};

export const FinancePage: React.FC = () => {
  const { user, logout, hasPermission } = useAuth();
  const navigate = useNavigate();

  const [dashboard, setDashboard] = useState<PaymentsDashboard | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [acts, setActs] = useState<Act[]>([]);
  const [payouts, setPayouts] = useState<Payout[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState<'invoices' | 'acts' | 'payouts'>('invoices');

  const canView = hasPermission('finance', 'view');

  useEffect(() => {
    if (!canView) return;
    loadData();
  }, [canView]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [dashData, invoicesData, actsData, payoutsData] = await Promise.allSettled([
        financeApi.getDashboard(),
        financeApi.getInvoices({ limit: 10 }),
        financeApi.getActs({ limit: 10 }),
        financeApi.getPayouts({ limit: 10 }),
      ]);

      if (dashData.status === 'fulfilled') setDashboard(dashData.value);
      if (invoicesData.status === 'fulfilled') setInvoices(invoicesData.value);
      if (actsData.status === 'fulfilled') setActs(actsData.value);
      if (payoutsData.status === 'fulfilled') setPayouts(payoutsData.value);

      setError('');
    } catch (err: any) {
      console.error('Failed to load finance data:', err);
      setError('Не удалось загрузить финансовые данные');
    } finally {
      setLoading(false);
    }
  };

  if (!canView) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-white rounded-lg shadow p-8 max-w-md text-center">
          <div className="text-5xl mb-4">🔒</div>
          <h2 className="text-xl font-bold text-gray-900 mb-2">Доступ запрещён</h2>
          <p className="text-gray-600 mb-4">У вас нет прав для просмотра финансового раздела</p>
          <button
            onClick={() => navigate('/')}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            На главную
          </button>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Загрузка финансовых данных...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center space-x-6">
              <h1 className="text-xl font-bold text-gray-900">🚜 СпецТехника Про</h1>
              <button onClick={() => navigate('/')} className="text-gray-600 hover:text-gray-900">Dashboard</button>
              <button onClick={() => navigate('/vehicles')} className="text-gray-600 hover:text-gray-900">Техника</button>
              <button onClick={() => navigate('/requests')} className="text-gray-600 hover:text-gray-900">Заявки</button>
              <span className="text-blue-600 font-medium">Финансы</span>
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
          <h2 className="text-2xl font-bold text-gray-900 mb-6">Финансы</h2>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-6">
              {error}
            </div>
          )}

          {/* Metrics Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-medium text-gray-500">Общий доход</h3>
                <span className="text-3xl">💰</span>
              </div>
              <div className="text-3xl font-bold text-gray-900 mb-2">
                {formatMoney(dashboard?.total_revenue)}
              </div>
              <div className="text-sm text-gray-600">
                Счетов: {dashboard?.invoices_count || 0}
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-medium text-gray-500">Оплачено</h3>
                <span className="text-3xl">✅</span>
              </div>
              <div className="text-3xl font-bold text-green-600 mb-2">
                {formatMoney(dashboard?.total_paid)}
              </div>
              <div className="text-sm text-gray-600">
                Актов: {dashboard?.acts_count || 0}
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-medium text-gray-500">Комиссия</h3>
                <span className="text-3xl">📊</span>
              </div>
              <div className="text-3xl font-bold text-blue-600 mb-2">
                {formatMoney(dashboard?.total_commission_earned)}
              </div>
              <div className="text-sm text-gray-600">
                Заработано
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-medium text-gray-500">Задолженность</h3>
                <span className="text-3xl">⚠️</span>
              </div>
              <div className="text-3xl font-bold text-orange-600 mb-2">
                {formatMoney(dashboard?.total_outstanding)}
              </div>
              <div className="text-sm text-gray-600">
                Выплат: {dashboard?.payouts_count || 0}
              </div>
            </div>
          </div>

          {/* Tabs */}
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <div className="border-b border-gray-200">
              <nav className="flex">
                <button
                  onClick={() => setActiveTab('invoices')}
                  className={`px-6 py-3 text-sm font-medium border-b-2 ${
                    activeTab === 'invoices'
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  }`}
                >
                  Счета ({invoices.length})
                </button>
                <button
                  onClick={() => setActiveTab('acts')}
                  className={`px-6 py-3 text-sm font-medium border-b-2 ${
                    activeTab === 'acts'
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  }`}
                >
                  Акты ({acts.length})
                </button>
                <button
                  onClick={() => setActiveTab('payouts')}
                  className={`px-6 py-3 text-sm font-medium border-b-2 ${
                    activeTab === 'payouts'
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  }`}
                >
                  Выплаты ({payouts.length})
                </button>
              </nav>
            </div>

            <div className="p-6">
              {/* Invoices Tab */}
              {activeTab === 'invoices' && (
                <div>
                  <div className="flex justify-between items-center mb-4">
                    <h3 className="text-lg font-semibold text-gray-900">Последние счета</h3>
                    <button
                      onClick={() => navigate('/invoices')}
                      className="text-sm text-blue-600 hover:text-blue-900 font-medium"
                    >
                      Все счета →
                    </button>
                  </div>
                  {invoices.length === 0 ? (
                    <div className="text-center py-12 text-gray-500">
                      <div className="text-5xl mb-4">💰</div>
                      <p>Счетов пока нет</p>
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                          <tr>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">№</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Дата</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Срок</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Сумма</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Оплачено</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Статус</th>
                          </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                          {invoices.map((inv) => (
                            <tr key={inv.id} className="hover:bg-gray-50">
                              <td className="px-4 py-3 whitespace-nowrap text-sm font-mono text-gray-900">
                                {inv.document_number || `#${inv.id}`}
                              </td>
                              <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-600">
                                {formatDate(inv.invoice_date)}
                              </td>
                              <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-600">
                                {formatDate(inv.due_date)}
                              </td>
                              <td className="px-4 py-3 whitespace-nowrap text-sm font-semibold text-gray-900">
                                {formatMoney(inv.total)}
                              </td>
                              <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-600">
                                {formatMoney(inv.paid_amount)}
                              </td>
                              <td className="px-4 py-3 whitespace-nowrap">
                                <span className={`px-2 py-1 text-xs font-semibold rounded-full ${INVOICE_STATUS_LABELS[inv.status]?.color || 'bg-gray-100'}`}>
                                  {INVOICE_STATUS_LABELS[inv.status]?.label || inv.status}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}

              {/* Acts Tab */}
              {activeTab === 'acts' && (
                <div>
                  <div className="flex justify-between items-center mb-4">
                    <h3 className="text-lg font-semibold text-gray-900">Последние акты</h3>
                  </div>
                  {acts.length === 0 ? (
                    <div className="text-center py-12 text-gray-500">
                      <div className="text-5xl mb-4">📄</div>
                      <p>Актов пока нет</p>
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                          <tr>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">№</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Дата</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Сумма</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Статус</th>
                          </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                          {acts.map((act) => (
                            <tr key={act.id} className="hover:bg-gray-50">
                              <td className="px-4 py-3 whitespace-nowrap text-sm font-mono text-gray-900">
                                {act.document_number || `#${act.id}`}
                              </td>
                              <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-600">
                                {formatDate(act.act_date)}
                              </td>
                              <td className="px-4 py-3 whitespace-nowrap text-sm font-semibold text-gray-900">
                                {formatMoney(act.total_amount)}
                              </td>
                              <td className="px-4 py-3 whitespace-nowrap">
                                <span className={`px-2 py-1 text-xs font-semibold rounded-full ${ACT_STATUS_LABELS[act.status]?.color || 'bg-gray-100'}`}>
                                  {ACT_STATUS_LABELS[act.status]?.label || act.status}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}

              {/* Payouts Tab */}
              {activeTab === 'payouts' && (
                <div>
                  <div className="flex justify-between items-center mb-4">
                    <h3 className="text-lg font-semibold text-gray-900">Последние выплаты</h3>
                  </div>
                  {payouts.length === 0 ? (
                    <div className="text-center py-12 text-gray-500">
                      <div className="text-5xl mb-4">💸</div>
                      <p>Выплат пока нет</p>
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                          <tr>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">№</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Дата</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Сумма</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Статус</th>
                          </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                          {payouts.map((p) => (
                            <tr key={p.id} className="hover:bg-gray-50">
                              <td className="px-4 py-3 whitespace-nowrap text-sm font-mono text-gray-900">
                                {p.document_number || `#${p.id}`}
                              </td>
                              <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-600">
                                {formatDate(p.payout_date)}
                              </td>
                              <td className="px-4 py-3 whitespace-nowrap text-sm font-semibold text-gray-900">
                                {formatMoney(p.net_amount)}
                              </td>
                              <td className="px-4 py-3 whitespace-nowrap">
                                <span className={`px-2 py-1 text-xs font-semibold rounded-full ${PAYOUT_STATUS_LABELS[p.status]?.color || 'bg-gray-100'}`}>
                                  {PAYOUT_STATUS_LABELS[p.status]?.label || p.status}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default FinancePage;
