import React, { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import EmptyState from '../components/EmptyState';
import { showToast } from '../utils/toast';
import { financeApi } from '../api/finance';

interface SalaryRecord {
  id: number;
  employee_contractor_id: number;
  period_start: string;
  period_end: string;
  shifts_count: number;
  total_hours: number;
  total_km: number;
  salary_type: string;
  gross_amount: number;
  deductions: number;
  net_amount: number;
  calculation_details: any;
  status: string;
  created_at: string | null;
  approved_at: string | null;
}

interface SalarySummary {
  total_records: number;
  total_gross: number;
  total_net: number;
  approved_count: number;
  paid_count: number;
}

const SALARY_TYPE_LABELS: Record<string, string> = {
  fixed_shift: 'Фикс/смена',
  hourly: 'Почасовая',
  per_km: 'За пробег',
  shift_percent: '% от смены',
  combo: 'Комбинация',
};

const STATUS_STYLES: Record<string, string> = {
  draft: 'bg-yellow-100 text-yellow-800',
  approved: 'bg-green-100 text-green-800',
  paid: 'bg-blue-100 text-blue-800',
};

const formatMoney = (v: number) =>
  `${v.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ₽`;

const API_BASE = import.meta.env.VITE_API_URL || '';

export const SalariesPage: React.FC = () => {
  const now = new Date();
  const firstOfMonth = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().split('T')[0];
  const today = now.toISOString().split('T')[0];

  const [dateFrom, setDateFrom] = useState(firstOfMonth);
  const [dateTo, setDateTo] = useState(today);
  const [records, setRecords] = useState<SalaryRecord[]>([]);
  const [summary, setSummary] = useState<SalarySummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [calculating, setCalculating] = useState(false);

  useEffect(() => {
    loadData();
  }, [dateFrom, dateTo]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [recs, sum] = await Promise.allSettled([
        financeApi.getSalaryRecords({ date_from: dateFrom, date_to: dateTo, limit: 200 }),
        financeApi.getSalarySummary(dateFrom, dateTo),
      ]);
      if (recs.status === 'fulfilled') setRecords(recs.value);
      if (sum.status === 'fulfilled') setSummary(sum.value);
    } catch (err) {
      console.error('Failed to load salaries:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCalculate = async () => {
    try {
      setCalculating(true);
      const result = await financeApi.calculateSalaries(dateFrom, dateTo);
      const count = result.records?.length || 0;
      showToast.success(`✅ Рассчитано ${count} зарплат`);
      loadData();
    } catch (err: any) {
      showToast.error('Ошибка расчёта: ' + (err?.response?.data?.detail || err.message));
    } finally {
      setCalculating(false);
    }
  };

  const handleApprove = async (id: number) => {
    if (!confirm('Утвердить это начисление?')) return;
    try {
      await financeApi.approveSalaryRecord(id);
      showToast.success('✅ Начисление утверждено');
      loadData();
    } catch (err: any) {
      showToast.error('Ошибка: ' + (err?.response?.data?.detail || err.message));
    }
  };

  const pdfUrl = `${API_BASE}/api/v1/salaries/export/pdf?date_from=${dateFrom}&date_to=${dateTo}`;
  const excelUrl = `${API_BASE}/api/v1/salaries/export/excel?date_from=${dateFrom}&date_to=${dateTo}`;

  return (
    <Layout>
      <div className="px-4 py-6 sm:px-0">
        {/* Header */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-6 gap-4">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">💰 Зарплаты сотрудников</h2>
            <p className="text-sm text-gray-500 mt-1">
              Расчёт и управление зарплатами по сменам, часам, пробегу
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="border border-gray-300 rounded-md px-2 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
            />
            <span className="text-gray-400">—</span>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="border border-gray-300 rounded-md px-2 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
            />
            <button
              onClick={handleCalculate}
              disabled={calculating}
              className="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 transition-colors text-sm font-medium disabled:opacity-50"
            >
              {calculating ? '⏳ Расчёт...' : '🧮 Рассчитать'}
            </button>
            <button
              onClick={loadData}
              className="bg-gray-100 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-200 transition-colors text-sm"
            >
              🔄
            </button>
            <a
              href={pdfUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="bg-purple-600 text-white px-4 py-2 rounded-lg hover:bg-purple-700 transition-colors text-sm font-medium"
            >
              📄 PDF
            </a>
            <a
              href={excelUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="bg-emerald-600 text-white px-4 py-2 rounded-lg hover:bg-emerald-700 transition-colors text-sm font-medium"
            >
              📊 Excel
            </a>
          </div>
        </div>

        {/* Summary Cards */}
        {summary && summary.total_records > 0 && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-white rounded-lg shadow p-4">
              <div className="text-xs text-gray-500 uppercase">Начислений</div>
              <div className="text-2xl font-bold text-gray-900">{summary.total_records}</div>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <div className="text-xs text-gray-500 uppercase">Общая сумма</div>
              <div className="text-2xl font-bold text-green-600">{formatMoney(summary.total_gross)}</div>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <div className="text-xs text-gray-500 uppercase">К выплате</div>
              <div className="text-2xl font-bold text-blue-600">{formatMoney(summary.total_net)}</div>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <div className="text-xs text-gray-500 uppercase">Утверждено / Выплачено</div>
              <div className="text-2xl font-bold text-gray-900">
                {summary.approved_count} / {summary.paid_count}
              </div>
            </div>
          </div>
        )}

        {/* Table */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center h-40">
              <div className="w-8 h-8 border-4 border-blue-200 rounded-full animate-spin border-t-blue-600" />
            </div>
          ) : records.length === 0 ? (
            <div className="p-6">
              <EmptyState
                icon="💰"
                title="Нет начислений за выбранный период"
                description="Нажмите «Рассчитать» чтобы создать начисления зарплат для всех сотрудников."
                actionLabel="🧮 Рассчитать зарплаты"
                onAction={handleCalculate}
              />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Сотрудник</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Период</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Тип</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Смены</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Часы</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Начислено</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">К выплате</th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Статус</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Действия</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {records.map((r) => (
                    <tr key={r.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">
                        #{r.employee_contractor_id}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-600">
                        {new Date(r.period_start).toLocaleDateString('ru-RU')} —{' '}
                        {new Date(r.period_end).toLocaleDateString('ru-RU')}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-600">
                        {SALARY_TYPE_LABELS[r.salary_type] || r.salary_type}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-right text-gray-900">
                        {r.shifts_count}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-right text-gray-900">
                        {r.total_hours.toFixed(1)}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-right font-semibold text-gray-900">
                        {formatMoney(r.gross_amount)}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-right font-bold text-green-600">
                        {formatMoney(r.net_amount)}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-center">
                        <span className={`px-2 py-1 text-xs font-semibold rounded-full ${STATUS_STYLES[r.status] || 'bg-gray-100 text-gray-800'}`}>
                          {r.status === 'draft' ? 'Черновик' : r.status === 'approved' ? 'Утверждено' : r.status === 'paid' ? 'Выплачено' : r.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-right text-sm">
                        {r.status === 'draft' && (
                          <button
                            onClick={() => handleApprove(r.id)}
                            className="text-green-600 hover:text-green-900 font-medium px-2 py-1 rounded hover:bg-green-50 transition-colors"
                            title="Утвердить начисление"
                          >
                            ✅ Утвердить
                          </button>
                        )}
                        {r.calculation_details && (
                          <button
                            onClick={() => alert(JSON.stringify(r.calculation_details, null, 2))}
                            className="text-gray-400 hover:text-gray-600 ml-2"
                            title="Детали расчёта"
                          >
                            ℹ️
                          </button>
                        )}
                        <a
                          href={`${API_BASE}/api/v1/salaries/export/pdf?date_from=${r.period_start}&date_to=${r.period_end}&record_id=${r.id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-purple-600 hover:text-purple-900 ml-2"
                          title="Скачать расчётный листок"
                        >
                          📄
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
};

export default SalariesPage;