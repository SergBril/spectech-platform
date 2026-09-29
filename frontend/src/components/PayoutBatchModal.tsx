import React, { useState } from 'react';
import { financeApi, type PayoutBatchResult } from '../api/finance';
import { showToast } from '../utils/toast';

interface Props {
  onClose: () => void;
  onSuccess: () => void;
}

export const PayoutBatchModal: React.FC<Props> = ({ onClose, onSuccess }) => {
  const today = new Date();
  const firstDayOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);
  const lastDayOfMonth = new Date(today.getFullYear(), today.getMonth() + 1, 0);

  const [dateFrom, setDateFrom] = useState(firstDayOfMonth.toISOString().split('T')[0]);
  const [dateTo, setDateTo] = useState(lastDayOfMonth.toISOString().split('T')[0]);
  const [commissionRate, setCommissionRate] = useState(15);
  const [loading, setLoading] = useState(false);
  const [preview, setPreview] = useState<PayoutBatchResult | null>(null);
  const [step, setStep] = useState<'input' | 'preview' | 'result'>('input');

  const handlePreview = async () => {
    try {
      setLoading(true);
      const result = await financeApi.calculatePayoutsBatch({
        date_from: dateFrom,
        date_to: dateTo,
        commission_rate: commissionRate,
      });
      setPreview(result);
      setStep('preview');
    } catch (err: any) {
      showToast.error('Ошибка: ' + (err?.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async () => {
    try {
      setLoading(true);
      // Повторный вызов создаст выплаты (backend уже создаёт их в calculate)
      const result = await financeApi.calculatePayoutsBatch({
        date_from: dateFrom,
        date_to: dateTo,
        commission_rate: commissionRate,
      });
      setPreview(result);
      setStep('result');
      showToast.success(`Создано ${result.total_payouts} выплат на сумму ${result.total_net.toLocaleString('ru-RU')} ₽`);
      onSuccess();
    } catch (err: any) {
      showToast.error('Ошибка создания выплат: ' + (err?.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const formatMoney = (value: number) => {
    return value.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        {/* Заголовок */}
        <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex justify-between items-center">
          <h2 className="text-2xl font-bold text-gray-900">
            💰 Batch создание выплат
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-2xl"
            disabled={loading}
          >
            ×
          </button>
        </div>

        {/* Содержимое */}
        <div className="p-6 space-y-6">
          {/* Шаг 1: Ввод параметров */}
          {step === 'input' && (
            <>
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <p className="text-sm text-blue-800">
                  ℹ️ Этот инструмент автоматически создаст выплаты всем собственникам техники за указанный период
                  на основе завершённых сверок данных.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Дата начала периода
                  </label>
                  <input
                    type="date"
                    value={dateFrom}
                    onChange={(e) => setDateFrom(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Дата окончания периода
                  </label>
                  <input
                    type="date"
                    value={dateTo}
                    onChange={(e) => setDateTo(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Ставка комиссии платформы (%): <span className="font-bold text-blue-600">{commissionRate}%</span>
                </label>
                <input
                  type="range"
                  min="0"
                  max="50"
                  step="1"
                  value={commissionRate}
                  onChange={(e) => setCommissionRate(parseInt(e.target.value))}
                  className="w-full"
                />
                <div className="flex justify-between text-xs text-gray-500 mt-1">
                  <span>0%</span>
                  <span>25%</span>
                  <span>50%</span>
                </div>
              </div>

              <div className="bg-gray-50 rounded-lg p-4">
                <h3 className="text-sm font-semibold text-gray-900 mb-2">Как это работает:</h3>
                <ol className="text-sm text-gray-600 space-y-1 list-decimal list-inside">
                  <li>Система найдёт все завершённые сверки за период</li>
                  <li>Сгруппирует по (собственник, техника)</li>
                  <li>Посчитает: <code>gross = моточасы × ставка_собственника</code></li>
                  <li>Вычтет комиссию: <code>net = gross - (gross × {commissionRate}%)</code></li>
                  <li>Создаст Payout документ для каждой комбинации</li>
                </ol>
              </div>
            </>
          )}

          {/* Шаг 2: Превью */}
          {step === 'preview' && preview && (
            <>
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                <p className="text-sm text-yellow-800">
                  ⚠️ Проверьте данные перед созданием. После подтверждения будут созданы {preview.total_payouts} выплат.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="bg-white border border-gray-200 rounded-lg p-4">
                  <div className="text-sm text-gray-500">Всего выплат</div>
                  <div className="text-2xl font-bold text-gray-900">{preview.total_payouts}</div>
                </div>
                <div className="bg-white border border-gray-200 rounded-lg p-4">
                  <div className="text-sm text-gray-500">Gross</div>
                  <div className="text-2xl font-bold text-blue-600">{formatMoney(preview.total_gross)} ₽</div>
                </div>
                <div className="bg-white border border-gray-200 rounded-lg p-4">
                  <div className="text-sm text-gray-500">Комиссия ({preview.commission_rate}%)</div>
                  <div className="text-2xl font-bold text-orange-600">{formatMoney(preview.total_commission)} ₽</div>
                </div>
                <div className="bg-white border border-gray-200 rounded-lg p-4">
                  <div className="text-sm text-gray-500">К выплате (Net)</div>
                  <div className="text-2xl font-bold text-green-600">{formatMoney(preview.total_net)} ₽</div>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200 border border-gray-300">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Техника</th>
                      <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">М/ч</th>
                      <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">Смен</th>
                      <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Gross</th>
                      <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Комиссия</th>
                      <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Net</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {preview.payouts.map((p) => (
                      <tr key={p.payout_id} className="hover:bg-gray-50">
                        <td className="px-4 py-2 text-sm text-gray-900">{p.vehicle_name}</td>
                        <td className="px-4 py-2 text-sm text-center text-gray-600">{p.moto_hours.toFixed(2)}</td>
                        <td className="px-4 py-2 text-sm text-center text-gray-600">{p.shifts_count}</td>
                        <td className="px-4 py-2 text-sm text-right text-gray-900">{formatMoney(p.gross_amount)} ₽</td>
                        <td className="px-4 py-2 text-sm text-right text-orange-600">{formatMoney(p.commission)} ₽</td>
                        <td className="px-4 py-2 text-sm text-right font-bold text-green-600">{formatMoney(p.net_amount)} ₽</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {/* Шаг 3: Результат */}
          {step === 'result' && preview && (
            <>
              <div className="bg-green-50 border border-green-200 rounded-lg p-6 text-center">
                <div className="text-5xl mb-4">✅</div>
                <h3 className="text-xl font-bold text-green-900 mb-2">
                  Выплаты успешно созданы!
                </h3>
                <p className="text-sm text-green-700">
                  Создано {preview.total_payouts} выплат на общую сумму {formatMoney(preview.total_net)} ₽
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-white border border-gray-200 rounded-lg p-4 text-center">
                  <div className="text-sm text-gray-500">Всего</div>
                  <div className="text-2xl font-bold text-gray-900">{preview.total_payouts}</div>
                </div>
                <div className="bg-white border border-gray-200 rounded-lg p-4 text-center">
                  <div className="text-sm text-gray-500">Комиссия платформы</div>
                  <div className="text-2xl font-bold text-orange-600">{formatMoney(preview.total_commission)} ₽</div>
                </div>
                <div className="bg-white border border-gray-200 rounded-lg p-4 text-center">
                  <div className="text-sm text-gray-500">К выплате</div>
                  <div className="text-2xl font-bold text-green-600">{formatMoney(preview.total_net)} ₽</div>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Футер */}
        <div className="sticky bottom-0 bg-gray-50 border-t border-gray-200 px-6 py-4 flex justify-between gap-3">
          {step === 'input' && (
            <>
              <button
                onClick={onClose}
                disabled={loading}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 disabled:opacity-50"
              >
                Отмена
              </button>
              <button
                onClick={handlePreview}
                disabled={loading || !dateFrom || !dateTo}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
              >
                {loading ? 'Загрузка...' : 'Предпросмотр'}
              </button>
            </>
          )}

          {step === 'preview' && (
            <>
              <button
                onClick={() => setStep('input')}
                disabled={loading}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 disabled:opacity-50"
              >
                ← Назад
              </button>
              <button
                onClick={handleConfirm}
                disabled={loading}
                className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
              >
                {loading ? 'Создание...' : `Создать ${preview?.total_payouts || 0} выплат`}
              </button>
            </>
          )}

          {step === 'result' && (
            <button
              onClick={onClose}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 ml-auto"
            >
              Закрыть
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default PayoutBatchModal;
