import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { financeApi, type Invoice, type InvoiceStatus } from '../api/finance';
import InvoiceFormModal from '../components/InvoiceFormModal';
import PaymentModal from '../components/PaymentModal';
import DeleteConfirmDialog from '../components/DeleteConfirmDialog';
import Layout from '../components/Layout';

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  draft: { label: 'Черновик', color: 'bg-gray-100 text-gray-800' },
  sent: { label: 'Отправлен', color: 'bg-blue-100 text-blue-800' },
  paid: { label: 'Оплачен', color: 'bg-green-100 text-green-800' },
  partially_paid: { label: 'Частично', color: 'bg-yellow-100 text-yellow-800' },
  overdue: { label: 'Просрочен', color: 'bg-orange-100 text-orange-800' },
  cancelled: { label: 'Отменён', color: 'bg-red-100 text-red-800' },
};

const formatDate = (s: string) => (s ? new Date(s).toLocaleDateString('ru-RU') : '—');
const formatMoney = (v: string | number | null | undefined) => {
  if (v === null || v === undefined || v === '') return '—';
  const num = typeof v === 'string' ? parseFloat(v) : v;
  return `${num.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ₽`;
};

export const InvoicesPage: React.FC = () => {
  const { user, logout, hasPermission } = useAuth();
  const navigate = useNavigate();

  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingInvoice, setEditingInvoice] = useState<Invoice | null>(null);

  const [paymentTarget, setPaymentTarget] = useState<Invoice | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Invoice | null>(null);

  const canCreate = hasPermission('finance', 'create');
  const canEdit = hasPermission('finance', 'update');
  const canDelete = hasPermission('finance', 'delete');

  const loadInvoices = async () => {
    try {
      setLoading(true);
      const data = await financeApi.getInvoices({ limit: 100 });
      setInvoices(data);
      setError('');
    } catch (err: any) {
      console.error('Failed to load invoices:', err);
      setError('Не удалось загрузить счета');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadInvoices();
  }, []);

  const handleCreate = () => {
    setEditingInvoice(null);
    setIsFormOpen(true);
  };

  const handleEdit = (inv: Invoice) => {
    setEditingInvoice(inv);
    setIsFormOpen(true);
  };

  const handleSave = async (data: any) => {
    try {
      if (editingInvoice) {
        const updated = await financeApi.updateInvoice(editingInvoice.id, data);
        setInvoices(invoices.map((i) => (i.id === editingInvoice.id ? updated : i)));
      } else {
        const created = await financeApi.createInvoice(data);
        setInvoices([created, ...invoices]);
      }
      setIsFormOpen(false);
      setEditingInvoice(null);
    } catch (err: any) {
      console.error('Failed to save invoice:', err);
      const detail = err?.response?.data?.detail;
      if (Array.isArray(detail)) {
        alert('Ошибка валидации: ' + detail.map((d: any) => `${d.loc?.join('.')}: ${d.msg}`).join(', '));
      } else {
        alert('Ошибка: ' + (detail || err.message));
      }
      throw err;
    }
  };

  const handleSend = async (inv: Invoice) => {
    if (!confirm(`Отправить счёт ${inv.document_number} клиенту?`)) return;
    try {
      const updated = await financeApi.sendInvoice(inv.id);
      setInvoices(invoices.map((i) => (i.id === inv.id ? updated : i)));
    } catch (err: any) {
      alert('Ошибка отправки: ' + (err?.response?.data?.detail || err.message));
    }
  };

  const handleResendEmail = async (inv: Invoice) => {
    if (!confirm(`Отправить счёт ${inv.document_number} клиенту повторно с PDF вложением?`)) return;
    try {
      await financeApi.resendInvoiceEmail(inv.id);
      alert(`✅ Письмо с PDF отправлено клиенту`);
    } catch (err: any) {
      alert('Ошибка отправки: ' + (err?.response?.data?.detail || err.message));
    }
  };

  const handleDownloadPdf = async (inv: Invoice) => {
    try {
      const blob = await financeApi.downloadInvoicePdf(inv.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${inv.document_number || `invoice-${inv.id}`}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err: any) {
      alert('Ошибка скачивания PDF: ' + (err?.response?.data?.detail || err.message));
    }
  };

  const handlePaymentSuccess = () => {
    setPaymentTarget(null);
    loadInvoices();
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    try {
      await financeApi.deleteInvoice(deleteTarget.id);
      setInvoices(invoices.filter((i) => i.id !== deleteTarget.id));
      setDeleteTarget(null);
    } catch (err: any) {
      alert('Ошибка удаления: ' + (err?.response?.data?.detail || err.message));
    }
  };

  const getProgress = (inv: Invoice) => {
    const total = parseFloat(inv.total || '0');
    const paid = parseFloat(inv.paid_amount || '0');
    if (total === 0) return 0;
    return Math.min(100, (paid / total) * 100);
  };

  // ИСПРАВЛЕНО: Обертка загрузки в Layout
  if (loading) {
    return (
      <Layout>
        <div className="min-h-screen bg-gray-50 flex items-center justify-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="px-4 py-6 sm:px-0">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-2xl font-bold text-gray-900">Счета ({invoices.length})</h2>
          {canCreate && (
            <button onClick={handleCreate} className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">
              + Новый счёт
            </button>
          )}
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">{error}</div>
        )}

        <div className="bg-white shadow rounded-lg overflow-hidden">
          {invoices.length === 0 ? (
            <div className="p-12 text-center text-gray-500">
              <div className="text-5xl mb-4">💰</div>
              <p>Счетов пока нет</p>
            </div>
          ) : (
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">№</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Дата</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Срок</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Сумма</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Оплачено</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Прогресс</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Статус</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Действия</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {invoices.map((inv) => {
                  const progress = getProgress(inv);
                  const paid = parseFloat(inv.paid_amount || '0');
                  const total = parseFloat(inv.total || '0');
                  const canAcceptPayment = inv.status !== 'paid' && inv.status !== 'cancelled' && paid < total;

                  return (
                    <tr key={inv.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-mono text-gray-900">{inv.document_number}</td>
                      <td className="px-4 py-3 text-sm text-gray-600">{formatDate(inv.invoice_date)}</td>
                      <td className="px-4 py-3 text-sm text-gray-600">{formatDate(inv.due_date)}</td>
                      <td className="px-4 py-3 text-sm font-semibold text-gray-900">{formatMoney(inv.total)}</td>
                      <td className="px-4 py-3 text-sm text-green-600">{formatMoney(inv.paid_amount)}</td>
                      <td className="px-4 py-3 text-sm">
                        <div className="w-24 bg-gray-200 rounded-full h-2">
                          <div
                            className={`h-2 rounded-full ${progress === 100 ? 'bg-green-500' : 'bg-blue-500'}`}
                            style={{ width: `${progress}%` }}
                          ></div>
                        </div>
                        <div className="text-xs text-gray-500 mt-1">{progress.toFixed(0)}%</div>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-1 text-xs font-semibold rounded-full ${STATUS_LABELS[inv.status]?.color || 'bg-gray-100'}`}>
                          {STATUS_LABELS[inv.status]?.label || inv.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right text-sm space-x-1">
                        {inv.status === 'draft' && canEdit && (
                          <>
                            <button onClick={() => handleSend(inv)} className="text-blue-600 hover:text-blue-900">Отправить</button>
                            <span className="text-gray-300">|</span>
                            <button onClick={() => handleEdit(inv)} className="text-gray-600 hover:text-gray-900">Изменить</button>
                          </>
                        )}

                        {inv.status !== 'cancelled' && inv.status !== 'draft' && canEdit && (
                          <>
                            <button
                              onClick={() => handleResendEmail(inv)}
                              className="text-indigo-600 hover:text-indigo-900 font-medium"
                              title="Отправить PDF клиенту повторно"
                            >
                              📧 Email
                            </button>
                            <span className="text-gray-300">|</span>
                          </>
                        )}

                        {canAcceptPayment && canEdit && (
                          <>
                            <button onClick={() => setPaymentTarget(inv)} className="text-green-600 hover:text-green-900 font-medium">
                              💳 Принять оплату
                            </button>
                            <span className="text-gray-300">|</span>
                          </>
                        )}

                        <button onClick={() => handleDownloadPdf(inv)} className="text-purple-600 hover:text-purple-900">PDF</button>

                        {canDelete && inv.status === 'draft' && (
                          <>
                            <span className="text-gray-300">|</span>
                            <button onClick={() => setDeleteTarget(inv)} className="text-red-600 hover:text-red-900">Удалить</button>
                          </>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* 🆕 ИСПРАВЛЕНО: Рендеринг модалок */}
      {isFormOpen && (
        <InvoiceFormModal
          invoice={editingInvoice}
          onClose={() => {
            setIsFormOpen(false);
            setEditingInvoice(null);
          }}
          onSave={handleSave}
        />
      )}

      {paymentTarget && (
        <PaymentModal
          invoice={paymentTarget}
          onClose={() => setPaymentTarget(null)}
          onSuccess={handlePaymentSuccess}
        />
      )}

      {deleteTarget && (
        <DeleteConfirmDialog
          title="Удалить счёт?"
          message={`Счёт ${deleteTarget.document_number} будет удалён безвозвратно.`}
          onConfirm={confirmDelete}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </Layout>
  );
};

export default InvoicesPage;