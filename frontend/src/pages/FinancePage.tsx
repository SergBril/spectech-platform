import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { financeApi, type Invoice, type Act, type Payout, type PaymentsDashboard, type ActCreate } from '../api/finance';
import { exportApi, downloadBlob } from '../api/export';
import { showToast } from '../utils/toast';
import { TableSkeleton, MetricCardSkeleton } from '../components/Skeleton';
import InvoiceFormModal from '../components/InvoiceFormModal';
import PaymentModal from '../components/PaymentModal';
import DeleteConfirmDialog from '../components/DeleteConfirmDialog';
import ActFormModal from '../components/ActFormModal';
import NotificationBell from '../components/NotificationBell';
import Navbar from '../components/Navbar';
import PayoutBatchModal from '../components/PayoutBatchModal';
import FinancialCharts from '../components/FinancialCharts';
import { financeApi as financeApiV2, type FinanceDashboardV2 } from '../api/finance';

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

  // Модальные окна
  const [editingInvoice, setEditingInvoice] = useState<Invoice | null>(null);
  const [isInvoiceFormOpen, setIsInvoiceFormOpen] = useState(false);
  const [editingAct, setEditingAct] = useState<Act | null>(null);
  const [isActFormOpen, setIsActFormOpen] = useState(false);
  const [paymentTarget, setPaymentTarget] = useState<Invoice | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Invoice | null>(null);
  const [deleteActTarget, setDeleteActTarget] = useState<Act | null>(null);
  // Период для расширенной аналитики
  const [periodPreset, setPeriodPreset] = useState<'month' | 'prev_month' | 'quarter' | 'year'>('month');
  const [dashboardV2, setDashboardV2] = useState<FinanceDashboardV2 | null>(null);

  // Вычисляем даты периода
  const getPeriodDates = () => {
    const now = new Date();
    let from: Date;
    let to: Date = now;

    switch (periodPreset) {
      case 'month':
        from = new Date(now.getFullYear(), now.getMonth(), 1);
        break;
      case 'prev_month':
        from = new Date(now.getFullYear(), now.getMonth() - 1, 1);
        to = new Date(now.getFullYear(), now.getMonth(), 0);
        break;
      case 'quarter':
        const quarterStart = Math.floor(now.getMonth() / 3) * 3;
        from = new Date(now.getFullYear(), quarterStart, 1);
        break;
      case 'year':
        from = new Date(now.getFullYear(), 0, 1);
        break;
    }

    return {
      from: from.toISOString().split('T')[0],
      to: to.toISOString().split('T')[0],
    };
  };

  const periodDates = getPeriodDates();
  const [isPayoutBatchModalOpen, setIsPayoutBatchModalOpen] = useState(false);

  const canView = hasPermission('finance', 'view');
  const canEdit = hasPermission('finance', 'update');
  const canDelete = hasPermission('finance', 'delete');
  const canCreate = hasPermission('finance', 'create');

  useEffect(() => {
    if (!canView) return;
    loadData();
  }, [canView]);

  useEffect(() => {
    if (!canView) return;
    loadDashboardV2();
  }, [canView, periodPreset]);

  const loadDashboardV2 = async () => {
    try {
      const data = await financeApiV2.getFinanceDashboardV2(periodDates.from, periodDates.to);
      setDashboardV2(data);
    } catch (err) {
      console.error('Failed to load dashboard V2:', err);
    }
  };

  const loadData = async () => {
    try {
      setLoading(true);
      const [dashData, invoicesData, actsData, payoutsData] = await Promise.allSettled([
        financeApi.getDashboard(),
        financeApi.getInvoices({ limit: 100 }),
        financeApi.getActs({ limit: 100 }),
        financeApi.getPayouts({ limit: 100 }),
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

  const handleGoToRequest = (requestId: number | null) => {
    if (requestId) navigate(`/requests/${requestId}`);
  };

  // === ИНВОЙСЫ ===
  const handleEditInvoice = (inv: Invoice) => setEditingInvoice(inv);

  const handleDeleteInvoice = async () => {
    if (!deleteTarget) return;
    try {
      await financeApi.deleteInvoice(deleteTarget.id);
      setInvoices(invoices.filter((i) => i.id !== deleteTarget.id));
      setDeleteTarget(null);
      showToast.success('Счёт удалён');
      loadData();
    } catch (err: any) {
      showToast.error('Ошибка удаления: ' + (err?.response?.data?.detail || err.message));
    }
  };

  const handleSendInvoice = async (inv: Invoice) => {
    if (!confirm(`Отправить счёт ${inv.document_number} клиенту?`)) return;
    try {
      const updated = await financeApi.sendInvoice(inv.id);
      setInvoices(invoices.map((i) => (i.id === inv.id ? updated : i)));
      showToast.success(`Счёт ${inv.document_number} отправлен`);
    } catch (err: any) {
      showToast.error('Ошибка отправки: ' + (err?.response?.data?.detail || err.message));
    }
  };

  // 🆕 Отправить счёт повторно (с PDF вложением)
  const handleResendInvoiceEmail = async (inv: Invoice) => {
    if (!confirm(`Отправить счёт ${inv.document_number} клиенту повторно с PDF вложением?`)) return;
    try {
      await financeApi.resendInvoiceEmail(inv.id);
      showToast.success(`✅ Письмо с PDF отправлено клиенту`);
    } catch (err: any) {
      showToast.error('Ошибка отправки: ' + (err?.response?.data?.detail || err.message));
    }
  };

  const handleCancelInvoice = async (inv: Invoice) => {
    if (!confirm(`Отменить счёт ${inv.document_number}?`)) return;
    try {
      const updated = await financeApi.updateInvoice(inv.id, { status: 'cancelled' } as any);
      setInvoices(invoices.map((i) => (i.id === inv.id ? updated : i)));
      showToast.success(`Счёт ${inv.document_number} отменён`);
    } catch (err: any) {
      showToast.error('Ошибка отмены: ' + (err?.response?.data?.detail || err.message));
    }
  };

  const handleDownloadPdf = async (type: 'invoice' | 'act' | 'payout', id: number, docNumber: string) => {
    try {
      let blob: Blob;
      if (type === 'invoice') blob = await financeApi.downloadInvoicePdf(id);
      else if (type === 'act') blob = await financeApi.downloadActPdf(id);
      else {
        showToast.warning('PDF для выплат пока не поддерживается');
        return;
      }
      downloadBlob(blob, `${docNumber}.pdf`);
      showToast.success('PDF скачан');
    } catch (err: any) {
      showToast.error('Ошибка скачивания: ' + (err?.response?.data?.detail || err.message));
    }
  };

  // 🆕 Скачать счёт-фактуру (только для ОСНО с НДС)
  const handleDownloadInvoiceFacture = async (act: Act) => {
    try {
      const blob = await financeApi.downloadInvoiceFacturePdf(act.id);
      downloadBlob(blob, `SF-${act.document_number}.pdf`);
      showToast.success('✅ Счёт-фактура скачана');
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (typeof detail === 'string' && detail.includes('ОСНО')) {
        showToast.error('❌ Счёт-фактура доступна только для ОСНО');
      } else {
        showToast.error('Ошибка: ' + (detail || err.message));
      }
    }
  };

  // 🆕 Скачать УПД (Универсальный передаточный документ)
  const handleDownloadUpd = async (act: Act) => {
    try {
      const blob = await financeApi.downloadUpdPdf(act.id);
      downloadBlob(blob, `UPD-${act.document_number}.pdf`);
      showToast.success('✅ УПД скачан');
    } catch (err: any) {
      showToast.error('Ошибка: ' + (err?.response?.data?.detail || err.message));
    }
  };

  // 🆕 Скачать ТОРГ-12 (Расходная накладная)
  const handleDownloadTorg12 = async (act: Act) => {
    try {
      const blob = await financeApi.downloadTorg12Pdf(act.id);
      downloadBlob(blob, `TORG-${act.document_number}.pdf`);
      showToast.success('✅ ТОРГ-12 скачан');
    } catch (err: any) {
      showToast.error('Ошибка: ' + (err?.response?.data?.detail || err.message));
    }
  };

  const handleSaveInvoice = async (data: any) => {
    try {
      if (editingInvoice) {
        const updated = await financeApi.updateInvoice(editingInvoice.id, data);
        setInvoices(invoices.map((i) => (i.id === editingInvoice.id ? updated : i)));
        showToast.success('Счёт обновлён');
      } else {
        const created = await financeApi.createInvoice(data);
        setInvoices([created, ...invoices]);
        showToast.success('Счёт создан');
      }
      setEditingInvoice(null);
      setIsInvoiceFormOpen(false);
      loadData();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (Array.isArray(detail)) {
        showToast.error('Ошибка валидации: ' + detail.map((d: any) => `${d.loc?.join('.')}: ${d.msg}`).join(', '));
      } else {
        showToast.error('Ошибка: ' + (detail || err.message));
      }
      throw err;
    }
  };

  const handlePaymentSuccess = () => {
    setPaymentTarget(null);
    loadData();
  };

  // === АКТЫ ===
  const handleSaveAct = async (data: ActCreate) => {
    try {
      if (editingAct) {
        const updated = await financeApi.updateAct(editingAct.id, data);
        setActs(acts.map((a) => (a.id === editingAct.id ? updated : a)));
      } else {
        const created = await financeApi.createAct(data);
        setActs([created, ...acts]);
      }
      showToast.success(editingAct ? 'Акт обновлён' : 'Акт создан');
      setEditingAct(null);
      setIsActFormOpen(false);
      loadData();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (Array.isArray(detail)) {
        showToast.error('Ошибка: ' + detail.map((d: any) => `${d.loc?.join('.')}: ${d.msg}`).join(', '));
      } else {
        showToast.error('Ошибка: ' + (detail || err.message));
      }
      throw err;
    }
  };

  const handleDeleteAct = async () => {
    if (!deleteActTarget) return;
    try {
      await financeApi.deleteAct(deleteActTarget.id);
      setActs(acts.filter((a) => a.id !== deleteActTarget.id));
      setDeleteActTarget(null);
      showToast.success('Акт удалён');
      loadData();
    } catch (err: any) {
      showToast.error('Ошибка удаления: ' + (err?.response?.data?.detail || err.message));
    }
  };

  const handleSignAct = async (act: Act, role: 'client' | 'executor') => {
    if (!confirm(`Подписать акт ${act.document_number} как ${role}?`)) return;
    try {
      const updated = await financeApi.signAct(act.id, role);
      setActs(acts.map((a) => (a.id === act.id ? updated : a)));
      showToast.success(`Акт подписан как ${role === 'client' ? 'клиент' : 'исполнитель'}`);
    } catch (err: any) {
      showToast.error('Ошибка подписания: ' + (err?.response?.data?.detail || err.message));
    }
  };

  // 🆕 Отправить акт повторно (с PDF вложением)
  const handleResendActEmail = async (act: Act) => {
    if (!confirm(`Отправить акт ${act.document_number} клиенту повторно с PDF вложением?`)) return;
    try {
      await financeApi.resendActEmail(act.id);
      showToast.success(`✅ Письмо с PDF отправлено клиенту`);
    } catch (err: any) {
      showToast.error('Ошибка отправки: ' + (err?.response?.data?.detail || err.message));
    }
  };

  // === ЭКСПОРТ ===
  const handleExportInvoicesCsv = async () => {
    try {
      const blob = await exportApi.invoicesCsv({});
      downloadBlob(blob, `invoices_${new Date().toISOString().slice(0, 10)}.csv`);
    } catch (err: any) {
      showToast.error('Ошибка экспорта: ' + (err?.response?.data?.detail || err.message));
    }
  };

  const handleExportActsCsv = async () => {
    try {
      const blob = await exportApi.actsCsv({});
      downloadBlob(blob, `acts_${new Date().toISOString().slice(0, 10)}.csv`);
    } catch (err: any) {
      showToast.error('Ошибка экспорта: ' + (err?.response?.data?.detail || err.message));
    }
  };

  if (!canView) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-white rounded-lg shadow p-8 max-w-md text-center">
          <div className="text-5xl mb-4">🔒</div>
          <h2 className="text-xl font-bold text-gray-900 mb-2">Доступ запрещён</h2>
          <button onClick={() => navigate('/')} className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
            На главную
          </button>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navbar />
        <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
          <div className="px-4 py-6 sm:px-0">
            <div className="flex justify-between items-center mb-6">
              <div className="w-40 h-8 bg-gray-200 rounded animate-pulse" />
              <div className="w-48 h-10 bg-gray-200 rounded animate-pulse" />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
              <MetricCardSkeleton />
              <MetricCardSkeleton />
              <MetricCardSkeleton />
              <MetricCardSkeleton />
            </div>
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <div className="border-b border-gray-200">
                <div className="flex space-x-2 p-2">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="w-32 h-10 bg-gray-100 rounded animate-pulse" />
                  ))}
                </div>
              </div>
              <div className="p-6">
                <TableSkeleton rows={5} columns={7} />
              </div>
            </div>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold text-gray-900">Финансы</h2>
            <button onClick={() => navigate('/invoices')} className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">
              Управление счетами →
            </button>
          </div>

          {error && <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-6">{error}</div>}

          {/* Period Selector */}
          <div className="bg-white rounded-lg shadow p-4 mb-6 flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-gray-700">Период:</span>
              <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
                {[
                  { key: 'month', label: 'Этот месяц' },
                  { key: 'prev_month', label: 'Прошлый месяц' },
                  { key: 'quarter', label: 'Квартал' },
                  { key: 'year', label: 'Год' },
                ].map((p) => (
                  <button
                    key={p.key}
                    onClick={() => setPeriodPreset(p.key as any)}
                    className={`px-3 py-1 text-sm rounded-md transition-colors ${
                      periodPreset === p.key
                        ? 'bg-blue-600 text-white'
                        : 'text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="text-sm text-gray-500">
              {new Date(periodDates.from).toLocaleDateString('ru-RU')} — {new Date(periodDates.to).toLocaleDateString('ru-RU')}
            </div>
          </div>

          {/* Metrics Cards (расширенные) */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-medium text-gray-500">Выручка</h3>
                <span className="text-3xl">💰</span>
              </div>
              <div className="text-3xl font-bold text-gray-900 mb-2">
                {formatMoney(dashboardV2?.revenue.total ?? dashboard?.total_revenue)}
              </div>
              <div className="text-sm text-gray-600">
                Оплачено: {formatMoney(dashboardV2?.revenue.paid ?? dashboard?.total_paid)}
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-medium text-gray-500">Прибыль</h3>
                <span className="text-3xl">📈</span>
              </div>
              <div className="text-3xl font-bold text-green-600 mb-2">
                {formatMoney(dashboardV2?.profit.gross ?? 0)}
              </div>
              <div className="text-sm text-gray-600">
                Маржа: <span className="font-semibold text-green-600">{dashboardV2?.profit.margin_percent.toFixed(1) ?? '—'}%</span>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-medium text-gray-500">Средний чек</h3>
                <span className="text-3xl">🧾</span>
              </div>
              <div className="text-3xl font-bold text-blue-600 mb-2">
                {formatMoney(dashboardV2?.metrics.avg_invoice ?? 0)}
              </div>
              <div className="text-sm text-gray-600">
                Счетов: {dashboardV2?.metrics.invoices_count ?? dashboard?.invoices_count ?? 0}
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-medium text-gray-500">Моточасы</h3>
                <span className="text-3xl">⏱️</span>
              </div>
              <div className="text-3xl font-bold text-purple-600 mb-2">
                {(dashboardV2?.metrics.moto_hours_total ?? 0).toLocaleString('ru-RU', { maximumFractionDigits: 1 })}
              </div>
              <div className="text-sm text-gray-600">
                Выплат: {dashboardV2?.metrics.payouts_count ?? dashboard?.payouts_count ?? 0}
              </div>
            </div>
          </div>

          {/* Графики: Top clients + Top vehicles */}
          <FinancialCharts dateFrom={periodDates.from} dateTo={periodDates.to} />

          {/* Tabs */}
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <div className="border-b border-gray-200">
              <nav className="flex">
                {(['invoices', 'acts', 'payouts'] as const).map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={`px-6 py-3 text-sm font-medium border-b-2 ${
                      activeTab === tab ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'
                    }`}
                  >
                    {tab === 'invoices' ? `Счета (${invoices.length})` : tab === 'acts' ? `Акты (${acts.length})` : `Выплаты (${payouts.length})`}
                  </button>
                ))}
              </nav>
            </div>

            <div className="p-6">
              {/* === СЧЕТА === */}
              {activeTab === 'invoices' && (
                <div>
                  <div className="flex justify-end mb-4 gap-2">
                    <button
                      onClick={handleExportInvoicesCsv}
                      className="bg-green-600 text-white px-3 py-2 rounded hover:bg-green-700 text-sm"
                      title="Экспорт всех счетов в CSV"
                    >
                      📥 Экспорт CSV
                    </button>
                    {canCreate && (
                      <button
                        onClick={() => { setEditingInvoice(null); setIsInvoiceFormOpen(true); }}
                        className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 text-sm"
                      >
                        + Новый счёт
                      </button>
                    )}
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
                            <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Действия</th>
                          </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                          {invoices.map((inv) => {
                            const paid = parseFloat(inv.paid_amount || '0');
                            const total = parseFloat(inv.total || '0');
                            const canAcceptPayment = inv.status !== 'paid' && inv.status !== 'cancelled' && paid < total;
                            // 🆕 Статусы, для которых показываем кнопку 📧
                            const canResendEmail = ['sent', 'paid', 'partially_paid', 'overdue'].includes(inv.status);
                            return (
                              <tr key={inv.id} className="hover:bg-gray-50">
                                <td className="px-4 py-3 whitespace-nowrap">
                                  <button onClick={() => handleGoToRequest(inv.request_id)} className="text-sm font-mono text-blue-600 hover:text-blue-900 hover:underline">
                                    {inv.document_number || `#${inv.id}`}
                                  </button>
                                </td>
                                <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-600">{formatDate(inv.invoice_date)}</td>
                                <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-600">{formatDate(inv.due_date)}</td>
                                <td className="px-4 py-3 whitespace-nowrap text-sm font-semibold text-gray-900">{formatMoney(inv.total)}</td>
                                <td className="px-4 py-3 whitespace-nowrap text-sm text-green-600">{formatMoney(inv.paid_amount)}</td>
                                <td className="px-4 py-3 whitespace-nowrap">
                                  <span className={`px-2 py-1 text-xs font-semibold rounded-full ${INVOICE_STATUS_LABELS[inv.status]?.color || 'bg-gray-100'}`}>
                                    {INVOICE_STATUS_LABELS[inv.status]?.label || inv.status}
                                  </span>
                                </td>
                                <td className="px-4 py-3 whitespace-nowrap text-right text-sm space-x-2">
                                  <button onClick={() => handleDownloadPdf('invoice', inv.id, inv.document_number)} className="text-purple-600 hover:text-purple-900" title="PDF">📄</button>
                                  {inv.status === 'draft' && canEdit && (
                                    <>
                                      <button onClick={() => handleSendInvoice(inv)} className="text-blue-600 hover:text-blue-900" title="Отправить">✉️</button>
                                      <button onClick={() => handleEditInvoice(inv)} className="text-gray-600 hover:text-gray-900" title="Редактировать">✏️</button>
                                      {canDelete && <button onClick={() => setDeleteTarget(inv)} className="text-red-600 hover:text-red-900" title="Удалить">🗑️</button>}
                                    </>
                                  )}
                                  {canAcceptPayment && canEdit && (
                                    <button onClick={() => setPaymentTarget(inv)} className="text-green-600 hover:text-green-900 font-medium" title="Принять оплату">💳</button>
                                  )}
                                  {/* 🆕 Кнопка "📧 Email" для sent/paid/partially_paid/overdue */}
                                  {canResendEmail && canEdit && (
                                    <button onClick={() => handleResendInvoiceEmail(inv)} className="text-indigo-600 hover:text-indigo-900" title="Отправить PDF клиенту повторно">📧</button>
                                  )}
                                  {['sent', 'overdue', 'partially_paid'].includes(inv.status) && canEdit && (
                                    <button onClick={() => handleCancelInvoice(inv)} className="text-orange-600 hover:text-orange-900" title="Отменить">❌</button>
                                  )}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}

              {/* === АКТЫ === */}
              {activeTab === 'acts' && (
                <div>
                  <div className="flex justify-end mb-4 gap-2">
                    <button
                      onClick={handleExportActsCsv}
                      className="bg-green-600 text-white px-3 py-2 rounded hover:bg-green-700 text-sm"
                      title="Экспорт всех актов в CSV"
                    >
                      📥 Экспорт CSV
                    </button>
                    {canCreate && (
                      <button
                        onClick={() => { setEditingAct(null); setIsActFormOpen(true); }}
                        className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 text-sm"
                      >
                        + Новый акт
                      </button>
                    )}
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
                            <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Действия</th>
                          </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                          {acts.map((act) => {
                            // 🆕 Статусы, для которых показываем кнопку 📧
                            const canResendEmail = ['sent', 'paid', 'overdue'].includes(act.status);
                            return (
                              <tr key={act.id} className="hover:bg-gray-50">
                                <td className="px-4 py-3 whitespace-nowrap">
                                  <button onClick={() => handleGoToRequest(act.request_id)} className="text-sm font-mono text-blue-600 hover:text-blue-900 hover:underline">
                                    {act.document_number || `#${act.id}`}
                                  </button>
                                </td>
                                <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-600">{formatDate(act.act_date)}</td>
                                <td className="px-4 py-3 whitespace-nowrap text-sm font-semibold text-gray-900">{formatMoney(act.total_amount)}</td>
                                <td className="px-4 py-3 whitespace-nowrap">
                                  <span className={`px-2 py-1 text-xs font-semibold rounded-full ${ACT_STATUS_LABELS[act.status]?.color || 'bg-gray-100'}`}>
                                    {ACT_STATUS_LABELS[act.status]?.label || act.status}
                                  </span>
                                </td>
                                <td className="px-4 py-3 whitespace-nowrap text-right text-sm space-x-2">
                                  <button onClick={() => handleDownloadPdf('act', act.id, act.document_number)} className="text-purple-600 hover:text-purple-900" title="Акт PDF">📄</button>
                                  {/* 🆕 Кнопка УПД (для всех актов) */}
                                  <button
                                    onClick={() => handleDownloadUpd(act)}
                                    className="text-green-600 hover:text-green-900 font-semibold"
                                    title="УПД (Универсальный передаточный документ)"
                                  >
                                    📋УПД
                                  </button>
                                  {/* 🆕 Кнопка ТОРГ-12 (расходная накладная для товаров) */}
                                  <button
                                    onClick={() => handleDownloadTorg12(act)}
                                    className="text-purple-600 hover:text-purple-900"
                                    title="ТОРГ-12 (Расходная накладная для товаров)"
                                  >
                                    📦Т-12
                                  </button>
                                  {/* 🆕 Кнопка "Счёт-фактура" — только для ОСНО с НДС (legacy) */}
                                  {act.tax_system === 'osno' && parseFloat(act.vat_rate || '0') > 0 && (
                                    <button
                                      onClick={() => handleDownloadInvoiceFacture(act)}
                                      className="text-orange-600 hover:text-orange-900"
                                      title="Счёт-фактура (для ОСНО, legacy)"
                                    >
                                      🧾
                                    </button>
                                  )}                                  {act.status === 'draft' && canEdit && (
                                    <>
                                      <button onClick={() => setEditingAct(act)} className="text-gray-600 hover:text-gray-900" title="Редактировать">✏️</button>
                                      <button
                                        onClick={() => handleSignAct(act, 'client')}
                                        className={act.signed_by_client_at ? 'text-gray-400' : 'text-green-600 hover:text-green-900'}
                                        title={act.signed_by_client_at ? 'Уже подписан клиентом' : 'Подписать (клиент)'}
                                        disabled={!!act.signed_by_client_at}
                                      >
                                        {act.signed_by_client_at ? '✅' : '✍️👤'}
                                      </button>
                                      <button
                                        onClick={() => handleSignAct(act, 'executor')}
                                        className={act.signed_by_executor_at ? 'text-gray-400' : 'text-blue-600 hover:text-blue-900'}
                                        title={act.signed_by_executor_at ? 'Уже подписан исполнителем' : 'Подписать (исполнитель)'}
                                        disabled={!!act.signed_by_executor_at}
                                      >
                                        {act.signed_by_executor_at ? '✅' : '✍️🏢'}
                                      </button>
                                      {canDelete && <button onClick={() => setDeleteActTarget(act)} className="text-red-600 hover:text-red-900" title="Удалить">🗑️</button>}
                                    </>
                                  )}
                                  {/* 🆕 Кнопка "📧 Email" для sent/paid/overdue */}
                                  {canResendEmail && canEdit && (
                                    <button onClick={() => handleResendActEmail(act)} className="text-indigo-600 hover:text-indigo-900" title="Отправить PDF клиенту повторно">📧</button>
                                  )}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}

              {/* === ВЫПЛАТЫ === */}
              {activeTab === 'payouts' && (
                <div>
                  <div className="flex justify-end mb-4 gap-2">
                    {canCreate && (
                      <button
                        onClick={() => setIsPayoutBatchModalOpen(true)}
                        className="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700 text-sm font-semibold"
                      >
                        💰 Batch создать выплаты
                      </button>
                    )}
                  </div>
                  {payouts.length === 0 ? (
                    <div className="text-center py-12 text-gray-500">
                      <div className="text-5xl mb-4">💸</div>
                      <p>Выплат пока нет</p>
                      <p className="text-sm mt-2">Нажмите "Batch создать выплаты" для массового создания</p>
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                          <tr>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">№</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Дата</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Gross</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Комиссия</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Net</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Статус</th>
                            <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Действия</th>
                          </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                          {payouts.map((p) => (
                            <tr key={p.id} className="hover:bg-gray-50">
                              <td className="px-4 py-3 whitespace-nowrap">
                                <span className="text-sm font-mono text-gray-900">
                                  {p.document_number || `#${p.id}`}
                                </span>
                              </td>
                              <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-600">{formatDate(p.payout_date)}</td>
                              <td className="px-4 py-3 whitespace-nowrap text-sm font-semibold text-gray-900">{formatMoney(p.gross_amount)}</td>
                              <td className="px-4 py-3 whitespace-nowrap text-sm text-orange-600">{formatMoney(p.platform_commission)}</td>
                              <td className="px-4 py-3 whitespace-nowrap text-sm font-bold text-green-600">{formatMoney(p.net_amount)}</td>
                              <td className="px-4 py-3 whitespace-nowrap">
                                <span className={`px-2 py-1 text-xs font-semibold rounded-full ${PAYOUT_STATUS_LABELS[p.status]?.color || 'bg-gray-100'}`}>
                                  {PAYOUT_STATUS_LABELS[p.status]?.label || p.status}
                                </span>
                              </td>
                              <td className="px-4 py-3 whitespace-nowrap text-right text-sm space-x-2">
                                {p.status === 'draft' && canEdit && (
                                  <button
                                    onClick={async () => {
                                      try {
                                        await financeApi.approvePayout(p.id);
                                        showToast.success('Выплата одобрена');
                                        loadData();
                                      } catch (err: any) {
                                        showToast.error('Ошибка: ' + (err?.response?.data?.detail || err.message));
                                      }
                                    }}
                                    className="text-blue-600 hover:text-blue-900 font-medium"
                                    title="Одобрить"
                                  >
                                    ✓ Одобрить
                                  </button>
                                )}
                                {p.status === 'sent' && canEdit && (
                                  <button
                                    onClick={async () => {
                                      try {
                                        await financeApi.payPayout(p.id);
                                        showToast.success('Выплата отмечена как выплаченная');
                                        loadData();
                                      } catch (err: any) {
                                        showToast.error('Ошибка: ' + (err?.response?.data?.detail || err.message));
                                      }
                                    }}
                                    className="text-green-600 hover:text-green-900 font-medium"
                                    title="Отметить как выплаченную"
                                  >
                                    💸 Выплатить
                                  </button>
                                )}
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

      {editingInvoice && (
        <InvoiceFormModal invoice={editingInvoice} onClose={() => setEditingInvoice(null)} onSave={handleSaveInvoice} />
      )}

      {isInvoiceFormOpen && !editingInvoice && (
        <InvoiceFormModal invoice={null} onClose={() => setIsInvoiceFormOpen(false)} onSave={handleSaveInvoice} />
      )}

      {editingAct !== null && (
        <ActFormModal act={editingAct} onClose={() => setEditingAct(null)} onSave={handleSaveAct} />
      )}

      {isActFormOpen && editingAct === null && (
        <ActFormModal act={null} onClose={() => setIsActFormOpen(false)} onSave={handleSaveAct} />
      )}

      {paymentTarget && (
        <PaymentModal invoice={paymentTarget} onClose={() => setPaymentTarget(null)} onSuccess={handlePaymentSuccess} />
      )}

      {deleteTarget && (
        <DeleteConfirmDialog vehicleName={`счёт ${deleteTarget.document_number}`} onConfirm={handleDeleteInvoice} onCancel={() => setDeleteTarget(null)} />
      )}

      {deleteActTarget && (
        <DeleteConfirmDialog vehicleName={`акт ${deleteActTarget.document_number}`} onConfirm={handleDeleteAct} onCancel={() => setDeleteActTarget(null)} />
      )}
      {isPayoutBatchModalOpen && (
        <PayoutBatchModal
          onClose={() => setIsPayoutBatchModalOpen(false)}
          onSuccess={() => {
            setIsPayoutBatchModalOpen(false);
            loadData();
          }}
        />
      )}
    </div>
  );
};

export default FinancePage;
