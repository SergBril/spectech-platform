import React, { useEffect, useState } from 'react';
import { financeApi, type Payout, type PayoutBatchResult } from '../api/finance';
import Layout from '../components/Layout';

const formatMoney = (v: string | number) =>
  new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 0 }).format(Number(v));

const formatDate = (d: string) => d ? new Date(d).toLocaleDateString('ru-RU') : '—';

const statusBadge = (s: string) => {
  const map: Record<string, string> = {
    draft: 'bg-gray-100 text-gray-700',
    sent: 'bg-blue-100 text-blue-700',
    approved: 'bg-indigo-100 text-indigo-700',
    paid: 'bg-green-100 text-green-700',
    overdue: 'bg-red-100 text-red-700',
    cancelled: 'bg-yellow-100 text-yellow-700',
  };
  const labels: Record<string, string> = {
    draft: 'Черновик', sent: 'Отправлено', approved: 'Одобрено',
    paid: 'Оплачено', overdue: 'Просрочено', cancelled: 'Отменено',
  };
  return <span className={`px-2 py-1 rounded-full text-xs font-medium ${map[s] || map.draft}`}>{labels[s] || s}</span>;
};

export const PayoutsPage: React.FC = () => {
  const [payouts, setPayouts] = useState<Payout[]>([]);
  const [loading, setLoading] = useState(true);
  const [calcLoading, setCalcLoading] = useState(false);
  const [calcResult, setCalcResult] = useState<PayoutBatchResult | null>(null);
  const [dateFrom, setDateFrom] = useState(() => {
    const d = new Date(); d.setDate(1); return d.toISOString().slice(0, 10);
  });
  const [dateTo, setDateTo] = useState(() => new Date().toISOString().slice(0, 10));

  const loadPayouts = async () => {
    try {
      setLoading(true);
      const data = await financeApi.getPayouts({ limit: 200 });
      setPayouts(Array.isArray(data) ? data : []);
    } catch { /* ignore */ } finally { setLoading(false); }
  };

  useEffect(() => { loadPayouts(); }, []);

  const handleCalculate = async () => {
    try {
      setCalcLoading(true);
      const result = await financeApi.calculatePayoutsBatch({ date_from: dateFrom, date_to: dateTo });
      setCalcResult(result);
      await loadPayouts();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Ошибка расчёта');
    } finally { setCalcLoading(false); }
  };

  const handleApprove = async (id: number) => {
    if (!confirm('Одобрить выплату?')) return;
    try {
      await financeApi.approvePayout(id);
      await loadPayouts();
    } catch (err: any) { alert(err.response?.data?.detail || 'Ошибка'); }
  };

  const handlePay = async (id: number) => {
    if (!confirm('Отметить как оплаченную?')) return;
    try {
      await financeApi.payPayout(id);
      await loadPayouts();
    } catch (err: any) { alert(err.response?.data?.detail || 'Ошибка'); }
  };

  const totalGross = payouts.reduce((s, p) => s + Number(p.gross_amount), 0);
  const totalNet = payouts.reduce((s, p) => s + Number(p.net_amount), 0);
  const totalCommission = payouts.reduce((s, p) => s + Number(p.platform_commission), 0);

  return (
    <Layout>
      <div className="space-y-6">
        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-white rounded-xl shadow-sm p-5 border-l-4 border-blue-500">
            <p className="text-sm text-gray-500">Всего выплат</p>
            <p className="text-2xl font-bold text-gray-900">{payouts.length}</p>
          </div>
          <div className="bg-white rounded-xl shadow-sm p-5 border-l-4 border-green-500">
            <p className="text-sm text-gray-500">Gross</p>
            <p className="text-2xl font-bold text-gray-900">{formatMoney(totalGross)}</p>
          </div>
          <div className="bg-white rounded-xl shadow-sm p-5 border-l-4 border-orange-500">
            <p className="text-sm text-gray-500">Комиссия</p>
            <p className="text-2xl font-bold text-gray-900">{formatMoney(totalCommission)}</p>
          </div>
          <div className="bg-white rounded-xl shadow-sm p-5 border-l-4 border-emerald-500">
            <p className="text-sm text-gray-500">К выплате (Net)</p>
            <p className="text-2xl font-bold text-emerald-600">{formatMoney(totalNet)}</p>
          </div>
        </div>

        {/* Calculate Panel */}
        <div className="bg-white rounded-xl shadow-sm p-5">
          <h3 className="text-lg font-semibold mb-3">📊 Рассчитать выплаты за период</h3>
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">С</label>
              <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
                className="px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">По</label>
              <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
                className="px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
            </div>
            <button onClick={handleCalculate} disabled={calcLoading}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
              {calcLoading ? '⏳ Расчёт...' : '🔄 Рассчитать'}
            </button>
          </div>
          {calcResult && (
            <div className="mt-3 p-3 bg-blue-50 rounded-lg text-sm">
              ✅ Создано выплат: <b>{calcResult.total_payouts}</b> |
              Gross: <b>{formatMoney(calcResult.total_gross)}</b> |
              Net: <b>{formatMoney(calcResult.total_net)}</b>
            </div>
          )}
        </div>

        {/* Table */}
        <div className="bg-white rounded-xl shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase">№</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase">Дата</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase">Техника</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase">Моточасы</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase">Ставка</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase">Gross</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase">Комиссия</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase">Net</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase">Статус</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase">Источник</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase">Оплата</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase">Действия</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {loading ? (
                  <tr><td colSpan={10} className="px-4 py-8 text-center text-gray-400">Загрузка...</td></tr>
                ) : payouts.length === 0 ? (
                  <tr><td colSpan={10} className="px-4 py-8 text-center text-gray-400">Нет выплат</td></tr>
                ) : payouts.map(p => {
                  const det = p.calculation_details || {};
                  return (
                    <tr key={p.id} className="hover:bg-blue-50 transition-colors">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">{p.document_number}</td>
                      <td className="px-4 py-3 text-sm text-gray-600">{formatDate(p.payout_date)}</td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        {det.vehicle_name || `Vehicle #${p.vehicle_id}`}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">{det.moto_hours ?? '—'} ч</td>
                      <td className="px-4 py-3 text-sm text-gray-600">{det.owner_rate ?? '—'} ₽/ч</td>
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">{formatMoney(p.gross_amount)}</td>
                      <td className="px-4 py-3 text-sm text-orange-600">{formatMoney(p.platform_commission)}</td>
                      <td className="px-4 py-3 text-sm font-bold text-emerald-600">{formatMoney(p.net_amount)}</td>
                      <td className="px-4 py-3 text-sm">{statusBadge(p.status)}</td>
                    <td className="px-4 py-4 whitespace-nowrap text-sm">
                      {(p as any).source_channel === 'marketplace' ? (
                        <span className="px-2 py-0.5 bg-purple-100 text-purple-800 rounded-full text-xs font-medium">🏪 Маркетплейс</span>
                      ) : (
                        <span className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded-full text-xs font-medium">📋 Прямой</span>
                      )}
                    </td>
                    <td className="px-4 py-4 whitespace-nowrap text-sm">
                      {((p as any).calculation_details?.payment_terms_days || 7) > 7 ? (
                        <span className="px-2 py-0.5 bg-red-100 text-red-800 rounded-full text-xs font-medium">
                          ⏰ {(p as any).calculation_details?.payment_terms_days} дн.
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 bg-green-100 text-green-700 rounded-full text-xs">
                          ✅ 7 дн.
                        </span>
                      )}
                    </td>
                      <td className="px-4 py-3 text-sm space-x-1">
                        {p.status === 'draft' && (
                          <button onClick={() => handleApprove(p.id)}
                            className="px-2 py-1 bg-indigo-100 text-indigo-700 rounded text-xs hover:bg-indigo-200">✓ Одобрить</button>
                        )}
                        {((p.status as string) === 'sent' || (p.status as string) === 'sent') && (
                          <button onClick={() => handlePay(p.id)}
                            className="px-2 py-1 bg-green-100 text-green-700 rounded text-xs hover:bg-green-200">💳 Оплатить</button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default PayoutsPage;
