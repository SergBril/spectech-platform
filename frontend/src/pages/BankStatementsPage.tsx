import React, { useEffect, useState, useRef } from 'react';
import Layout from '../components/Layout';
import EmptyState from '../components/EmptyState';
import { showToast } from '../utils/toast';
import { financeApi } from '../api/finance';

interface BankStatement {
  id: number;
  file_name: string;
  status: string;
  date_start: string | null;
  date_end: string | null;
  total_transactions: number;
  matched_transactions: number;
  created_at: string | null;
}

interface UnmatchedPayment {
  id: number;
  bank_transaction_id: string;
  document_number: string;
  document_date: string;
  processed_date: string;
  amount: number;
  counterparty_name: string;
  counterparty_inn: string | null;
  purpose: string | null;
}

const formatMoney = (v: number) =>
  `${v.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ₽`;

const formatDate = (d: string | null) =>
  d ? new Date(d).toLocaleDateString('ru-RU') : '—';

export const BankStatementsPage: React.FC = () => {
  const [statements, setStatements] = useState<BankStatement[]>([]);
  const [unmatched, setUnmatched] = useState<UnmatchedPayment[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [activeTab, setActiveTab] = useState<'statements' | 'unmatched'>('statements');
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [stmts, unmatchData] = await Promise.allSettled([
        financeApi.getBankStatements(),
        financeApi.getUnmatchedPayments(),
      ]);
      if (stmts.status === 'fulfilled') setStatements(stmts.value);
      if (unmatchData.status === 'fulfilled') setUnmatched(unmatchData.value.items || []);
    } catch (err) {
      console.error('Failed to load bank data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.txt')) {
      showToast.error('Поддерживаются только файлы .txt (1CClientBankExchange)');
      return;
    }

    try {
      setUploading(true);
      const result = await financeApi.uploadBankStatement(file);
      showToast.success(
        `✅ Загружено: ${result.total_transactions} операций, ${result.matched_transactions} привязано автоматически`
      );
      loadData();
    } catch (err: any) {
      showToast.error('Ошибка загрузки: ' + (err?.response?.data?.detail || err.message));
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleApplyPayment = async (txId: number) => {
    const invoiceIdStr = prompt('Введите ID счёта для привязки платежа:');
    if (!invoiceIdStr) return;
    const invoiceId = parseInt(invoiceIdStr, 10);
    if (isNaN(invoiceId)) {
      showToast.error('Некорректный ID счёта');
      return;
    }

    try {
      await financeApi.applyPaymentToInvoice(txId, invoiceId);
      showToast.success('✅ Платёж привязан к счёту');
      loadData();
    } catch (err: any) {
      showToast.error('Ошибка: ' + (err?.response?.data?.detail || err.message));
    }
  };

  return (
    <Layout>
      <div className="px-4 py-6 sm:px-0">
        {/* Header */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-6 gap-4">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">🏦 Банковские выписки</h2>
            <p className="text-sm text-gray-500 mt-1">
              Загрузите выписку из банка для автоматической разноски платежей по счетам
            </p>
          </div>
          <div className="flex items-center gap-3">
            <input
              ref={fileInputRef}
              type="file"
              accept=".txt"
              onChange={handleFileUpload}
              className="hidden"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium disabled:opacity-50"
            >
              {uploading ? '⏳ Загрузка...' : '📤 Загрузить выписку'}
            </button>
            <button
              onClick={loadData}
              className="bg-gray-100 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-200 transition-colors text-sm"
            >
              🔄 Обновить
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="border-b border-gray-200">
            <nav className="flex">
              {[
                { key: 'statements', label: `📋 Выписки (${statements.length})` },
                { key: 'unmatched', label: `❓ Непривязанные (${unmatched.length})` },
              ].map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key as any)}
                  className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors ${
                    activeTab === tab.key
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </nav>
          </div>

          <div className="p-6">
            {loading ? (
              <div className="flex items-center justify-center h-40">
                <div className="w-8 h-8 border-4 border-blue-200 rounded-full animate-spin border-t-blue-600" />
              </div>
            ) : activeTab === 'statements' ? (
              /* === TAB: ВЫПИСКИ === */
              statements.length === 0 ? (
                <EmptyState
                  icon="🏦"
                  title="Выписки ещё не загружены"
                  description="Загрузите банковскую выписку в формате 1CClientBankExchange (.txt) для автоматической разноски платежей."
                  actionLabel="📤 Загрузить выписку"
                  onAction={() => fileInputRef.current?.click()}
                />
              ) : (
                <div className="overflow-x-auto overflow-y-auto max-h-[70vh] border border-gray-200 rounded">
            <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50 sticky top-0 z-10 shadow-sm">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Файл</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Период</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Операций</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Привязано</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Статус</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Загружено</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {statements.map((s) => (
                        <tr key={s.id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 whitespace-nowrap text-sm font-mono text-gray-900">
                            {s.file_name}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-600">
                            {formatDate(s.date_start)} — {formatDate(s.date_end)}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                            {s.total_transactions}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-sm">
                            <span className="text-green-600 font-semibold">{s.matched_transactions}</span>
                            {' / '}
                            <span className="text-gray-500">{s.total_transactions}</span>
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            <span className={`px-2 py-1 text-xs font-semibold rounded-full ${
                              s.status === 'processed'
                                ? 'bg-green-100 text-green-800'
                                : s.status === 'error'
                                ? 'bg-red-100 text-red-800'
                                : 'bg-yellow-100 text-yellow-800'
                            }`}>
                              {s.status === 'processed' ? 'Обработана' : s.status === 'error' ? 'Ошибка' : s.status}
                            </span>
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                            {formatDate(s.created_at)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
            ) : (
              /* === TAB: НЕПРИВЯЗАННЫЕ === */
              unmatched.length === 0 ? (
                <EmptyState
                  icon="✅"
                  title="Все платежи привязаны"
                  description="Нет непривязанных входящих платежей. Загрузите новую выписку или проверьте позже."
                />
              ) : (
                <div className="overflow-x-auto overflow-y-auto max-h-[70vh] border border-gray-200 rounded">
            <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50 sticky top-0 z-10 shadow-sm">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Дата</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Сумма</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Контрагент</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">ИНН</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Назначение</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Действия</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {unmatched.map((tx) => (
                        <tr key={tx.id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-600">
                            {formatDate(tx.processed_date)}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-sm font-bold text-green-600">
                            {formatMoney(tx.amount)}
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-900 max-w-[200px] truncate">
                            {tx.counterparty_name || '—'}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-sm font-mono text-gray-500">
                            {tx.counterparty_inn || '—'}
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-500 max-w-[300px] truncate" title={tx.purpose || ''}>
                            {tx.purpose || '—'}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-right text-sm">
                            <button
                              onClick={() => handleApplyPayment(tx.id)}
                              className="text-blue-600 hover:text-blue-900 font-medium px-3 py-1 rounded hover:bg-blue-50 transition-colors"
                              title="Привязать к счёту вручную"
                            >
                              🔗 Привязать
                            </button>
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
      </div>
    </Layout>
  );
};

export default BankStatementsPage;
