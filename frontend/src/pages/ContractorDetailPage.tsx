import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { contractorsApi, type Contractor } from '../api/contractors';
import { financeApi, type Invoice, type Act } from '../api/finance';
import { downloadBlob } from '../api/export';
import { showToast } from '../utils/toast';
import Layout from '../components/Layout'; // Layout уже здесь

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

const formatMoney = (v: string | number | null | undefined) => {
  if (v === null || v === undefined || v === '') return '—';
  const num = typeof v === 'string' ? parseFloat(v) : v;
  return `${num.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ₽`;
};

const formatDate = (iso: string | null) => {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('ru-RU');
};

export const ContractorDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { hasPermission } = useAuth();

  const [contractor, setContractor] = useState<Contractor | null>(null);
  const [invoices, setInvoices] = useState<any[]>([]);
  const [acts, setActs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [history, setHistory] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState<'invoices' | 'acts'>('invoices');
  const [finance, setFinance] = useState<any>(null);

  const canCreateFinance = hasPermission('finance', 'create');

  useEffect(() => {
    loadContractorData();
  }, [id]);

  const loadContractorData = async () => {
    try {
      setLoading(true);
  
      // 1. Загружаем основную информацию
      const contractorData = await contractorsApi.getById(Number(id));
      setContractor(contractorData);

      // 2. Загружаем финансовую сводку
      try {
        const financeData = await financeApi.getContractorSummary(Number(id));
        setFinance(financeData);
      } catch (financeErr) {
        console.warn('Finance summary not available:', financeErr);
        setFinance(null);
      }

      // 3. Загружаем счета контрагента
      try {
        const invoicesData = await financeApi.getInvoices({ 
          contractor_id: Number(id),
          limit: 100 
        });
        setInvoices(Array.isArray(invoicesData) ? invoicesData : []);
      } catch (invoicesErr) {
        console.warn('Invoices not available:', invoicesErr);
        setInvoices([]);
      }

      // 4. Загружаем акты контрагента
      try {
        const actsData = await financeApi.getActs({ 
          contractor_id: Number(id),
          limit: 100 
        });
        setActs(Array.isArray(actsData) ? actsData : []);
      } catch (actsErr) {
        console.warn('Acts not available:', actsErr);
        setActs([]);
      }

      // 5. Загружаем историю
      try {
        const historyData = await contractorsApi.getHistory(Number(id));
        setHistory(Array.isArray(historyData) ? historyData : []);
      } catch (historyErr) {
        console.warn('History not available:', historyErr);
        setHistory([]);
      }
    } catch (err: any) {
      console.error('Failed to load contractor:', err);
      showToast.error('Не удалось загрузить данные контрагента');
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadInvoicePdf = async (inv: Invoice) => {
    try {
      const blob = await financeApi.downloadInvoicePdf(inv.id);
      downloadBlob(blob, `${inv.document_number}.pdf`);
    } catch (err: any) {
      showToast.error('Ошибка: ' + err.message);
    }
  };

  const handleDownloadActPdf = async (act: Act) => {
    try {
      const blob = await financeApi.downloadActPdf(act.id);
      downloadBlob(blob, `${act.document_number}.pdf`);
    } catch (err: any) {
      showToast.error('Ошибка: ' + err.message);
    }
  };

  const handleDownloadFacture = async (act: Act) => {
    try {
      const blob = await financeApi.downloadInvoiceFacturePdf(act.id);
      downloadBlob(blob, `SF-${act.document_number}.pdf`);
    } catch (err: any) {
      showToast.error(err?.response?.data?.detail || err.message);
    }
  };

  // ИСПРАВЛЕНО: Обертка состояния загрузки в Layout
  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-96">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-gray-600">Загрузка...</p>
          </div>
        </div>
      </Layout>
    );
  }

  // ИСПРАВЛЕНО: Обертка состояния "не найден" в Layout
  if (!contractor) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-96">
          <div className="text-center">
            <div className="text-5xl mb-4">❌</div>
            <p className="text-gray-600">Контрагент не найден</p>
            <button onClick={() => navigate('/contractors')} className="mt-4 text-blue-600 hover:underline">
              ← Вернуться к списку
            </button>
          </div>
        </div>
      </Layout>
    );
  }

  const totalInvoicesAmount = invoices.reduce((sum, i) => sum + parseFloat(i.total || '0'), 0);
  const totalActsAmount = acts.reduce((sum, a) => sum + parseFloat(a.total_amount || '0'), 0);
  const totalPaid = invoices.reduce((sum, i) => sum + parseFloat(i.paid_amount || '0'), 0);

  // ИСПРАВЛЕНО: Убран Navbar, всё содержимое обернуто в Layout
  return (
    <Layout>
      {/* Кнопка назад */}
      <button
        onClick={() => navigate('/contractors')}
        className="mb-4 text-blue-600 hover:text-blue-900 flex items-center gap-2"
      >
        ← Вернуться к списку контрагентов
      </button>

      {/* === ШАПКА === */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <div className="flex justify-between items-start mb-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">{contractor.name}</h1>
            <p className="text-gray-600 mt-1">
              {contractor.type === 'client' && '👤 Клиент'}
              {contractor.type === 'owner' && '🚜 Собственник техники'}
              {contractor.type === 'subcontractor' && '🤝 Субподрядчик'}
            </p>
          </div>
          <div className="flex gap-2">
            {canCreateFinance && contractor.type === 'client' && (
              <>
                <button
                  onClick={() => navigate(`/invoices?new=1&client_id=${contractor.id}`)}
                  className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 text-sm"
                >
                  + Новый счёт
                </button>
                <button
                  onClick={() => navigate(`/acts/new?client_id=${contractor.id}`)}
                  className="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700 text-sm"
                >
                  + Новый акт
                </button>
              </>
            )}
            <button
              onClick={() => navigate('/contractors')}
              className="bg-gray-200 text-gray-800 px-4 py-2 rounded hover:bg-gray-300 text-sm"
            >
              ✏️ Редактировать
            </button>
          </div>
        </div>

        {/* KPI */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-blue-50 rounded-lg p-4">
            <p className="text-xs text-gray-600 uppercase font-semibold">Счетов</p>
            <p className="text-2xl font-bold text-blue-700">{invoices.length}</p>
            <p className="text-xs text-gray-600">{formatMoney(totalInvoicesAmount)}</p>
          </div>
          <div className="bg-green-50 rounded-lg p-4">
            <p className="text-xs text-gray-600 uppercase font-semibold">Оплачено</p>
            <p className="text-2xl font-bold text-green-700">{formatMoney(totalPaid)}</p>
            <p className="text-xs text-gray-600">
              {totalInvoicesAmount > 0 ? `${(totalPaid / totalInvoicesAmount * 100).toFixed(0)}%` : '0%'}
            </p>
          </div>
          <div className="bg-purple-50 rounded-lg p-4">
            <p className="text-xs text-gray-600 uppercase font-semibold">Актов</p>
            <p className="text-2xl font-bold text-purple-700">{acts.length}</p>
            <p className="text-xs text-gray-600">{formatMoney(totalActsAmount)}</p>
          </div>
          <div className="bg-orange-50 rounded-lg p-4">
            <p className="text-xs text-gray-600 uppercase font-semibold">Задолженность</p>
            <p className="text-2xl font-bold text-orange-700">{formatMoney(totalInvoicesAmount - totalPaid)}</p>
          </div>
        </div>

        {/* Реквизиты */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 text-sm">
          <div className="bg-gray-50 p-3 rounded">
            <p className="text-gray-500 text-xs uppercase font-semibold mb-1">ИНН / КПП</p>
            <p className="font-mono font-medium">
              {contractor.inn || '—'} {contractor.kpp && `/ ${contractor.kpp}`}
            </p>
          </div>
          <div className="bg-gray-50 p-3 rounded">
            <p className="text-gray-500 text-xs uppercase font-semibold mb-1">ОГРН</p>
            <p className="font-mono font-medium">{contractor.ogrn || '—'}</p>
          </div>
          <div className="bg-gray-50 p-3 rounded">
            <p className="text-gray-500 text-xs uppercase font-semibold mb-1">Система налогов</p>
            <p className="font-medium">
              {contractor.tax_system === 'osno' && 'ОСНО (с НДС)'}
              {contractor.tax_system === 'usn_6' && 'УСН "Доходы" (6%)'}
              {contractor.tax_system === 'usn_15' && 'УСН "Доходы-Расходы" (15%)'}
              {contractor.tax_system === 'patent' && 'Патент'}
              {contractor.tax_system === 'npd' && 'НПД / Самозанятый'}
              {!contractor.tax_system && '—'}
            </p>
          </div>
          <div className="bg-gray-50 p-3 rounded md:col-span-2 lg:col-span-3">
            <p className="text-gray-500 text-xs uppercase font-semibold mb-1">📍 Юридический адрес</p>
            <p className="text-gray-900">{contractor.legal_address || '—'}</p>
          </div>
          {contractor.bank_details && (
            <>
              <div className="bg-gray-50 p-3 rounded">
                <p className="text-gray-500 text-xs uppercase font-semibold mb-1">🏦 Банк</p>
                <p className="text-gray-900">{contractor.bank_details.bank_name || '—'}</p>
              </div>
              <div className="bg-gray-50 p-3 rounded">
                <p className="text-gray-500 text-xs uppercase font-semibold mb-1">р/с</p>
                <p className="font-mono text-xs">{contractor.bank_details.account || '—'}</p>
              </div>
              <div className="bg-gray-50 p-3 rounded">
                <p className="text-gray-500 text-xs uppercase font-semibold mb-1">БИК / к/с</p>
                <p className="font-mono text-xs">
                  {contractor.bank_details.bik || '—'} / {contractor.bank_details.correspondent_account || '—'}
                </p>
              </div>
            </>
          )}
          {(contractor.contact_name || contractor.contact_phone || contractor.contact_email) && (
            <>
              <div className="bg-gray-50 p-3 rounded md:col-span-2 lg:col-span-3">
                <p className="text-gray-500 text-xs uppercase font-semibold mb-1">👤 Контакты</p>
                <div className="flex gap-4 flex-wrap">
                  {contractor.contact_name && <span>👤 {contractor.contact_name}</span>}
                  {contractor.contact_phone && <span>📞 {contractor.contact_phone}</span>}
                  {contractor.contact_email && (
                    <a href={`mailto:${contractor.contact_email}`} className="text-blue-600 hover:underline">
                      ✉️ {contractor.contact_email}
                    </a>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* === ТАБЫ: Счета / Акты === */}
      <div className="bg-white rounded-lg shadow">
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
              💰 Счета ({invoices.length})
            </button>
            <button
              onClick={() => setActiveTab('acts')}
              className={`px-6 py-3 text-sm font-medium border-b-2 ${
                activeTab === 'acts'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              📋 Акты ({acts.length})
            </button>
          </nav>
        </div>

        <div className="p-6">
          {activeTab === 'invoices' && (
            invoices.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                <div className="text-5xl mb-4">💰</div>
                <p>Счетов для этого контрагента пока нет</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">№</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Дата</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Сумма</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Оплачено</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Статус</th>
                      <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Действия</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {invoices.map((inv) => (
                      <tr key={inv.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm font-mono">{inv.document_number}</td>
                        <td className="px-4 py-3 text-sm text-gray-600">{formatDate(inv.invoice_date)}</td>
                        <td className="px-4 py-3 text-sm font-semibold">{formatMoney(inv.total)}</td>
                        <td className="px-4 py-3 text-sm text-green-600">{formatMoney(inv.paid_amount)}</td>
                        <td className="px-4 py-3">
                          <span className={`px-2 py-1 text-xs font-semibold rounded-full ${INVOICE_STATUS_LABELS[inv.status]?.color}`}>
                            {INVOICE_STATUS_LABELS[inv.status]?.label || inv.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            onClick={() => handleDownloadInvoicePdf(inv)}
                            className="text-purple-600 hover:text-purple-900"
                            title="Скачать PDF"
                          >
                            📄 PDF
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          )}

          {activeTab === 'acts' && (
            acts.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                <div className="text-5xl mb-4">📋</div>
                <p>Актов для этого контрагента пока нет</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">№</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Дата</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Сумма</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Статус</th>
                      <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Действия</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {acts.map((act) => (
                      <tr key={act.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm font-mono">{act.document_number}</td>
                        <td className="px-4 py-3 text-sm text-gray-600">{formatDate(act.act_date)}</td>
                        <td className="px-4 py-3 text-sm font-semibold">{formatMoney(act.total_amount)}</td>
                        <td className="px-4 py-3">
                          <span className={`px-2 py-1 text-xs font-semibold rounded-full ${ACT_STATUS_LABELS[act.status]?.color}`}>
                            {ACT_STATUS_LABELS[act.status]?.label || act.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right text-sm space-x-2">
                          <button
                            onClick={() => handleDownloadActPdf(act)}
                            className="text-purple-600 hover:text-purple-900"
                            title="Акт PDF"
                          >
                            📄 Акт
                          </button>
                          {act.tax_system === 'osno' && parseFloat(act.vat_rate || '0') > 0 && (
                            <button
                              onClick={() => handleDownloadFacture(act)}
                              className="text-orange-600 hover:text-orange-900"
                              title="Счёт-фактура"
                            >
                              🧾 СФ
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          )}
        </div>
      </div>
    </Layout>
  );
};

export default ContractorDetailPage;