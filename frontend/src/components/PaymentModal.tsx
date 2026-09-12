import React, { useState } from 'react';
import type { Invoice, PaymentCreate, PaymentMethod } from '../api/finance';
import { financeApi } from '../api/finance';

interface Props {
  invoice: Invoice;
  onClose: () => void;
  onSuccess: () => void;
}

const PAYMENT_METHODS: { value: PaymentMethod; label: string }[] = [
  { value: 'bank_transfer', label: '🏦 Банковский перевод' },
  { value: 'card', label: '💳 Карта' },
  { value: 'cash', label: '💵 Наличные' },
  { value: 'other', label: '📄 Другое' },
];

const formatMoney = (v: string | number) => {
  const num = typeof v === 'string' ? parseFloat(v) : v;
  return `${num.toLocaleString('ru-RU', { minimumFractionDigits: 2 })} ₽`;
};

export const PaymentModal: React.FC<Props> = ({ invoice, onClose, onSuccess }) => {
  const total = parseFloat(invoice.total || '0');
  const paid = parseFloat(invoice.paid_amount || '0');
  const remaining = total - paid;

  const [amount, setAmount] = useState(remaining.toFixed(2));
  const [method, setMethod] = useState<PaymentMethod>('bank_transfer');
  const [paymentDate, setPaymentDate] = useState(new Date().toISOString().substring(0, 10));
  const [externalId, setExternalId] = useState('');
  const [comment, setComment] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    const amountNum = parseFloat(amount);
    if (isNaN(amountNum) || amountNum <= 0) {
      setError('Введите корректную сумму');
      return;
    }
    if (amountNum > remaining) {
      setError(`Сумма не может превышать остаток (${formatMoney(remaining)})`);
      return;
    }

    setSaving(true);
    try {
      const data: PaymentCreate = {
        invoice_id: invoice.id,
        amount: amountNum,
        method,
        payment_date: paymentDate,
        external_transaction_id: externalId.trim() || undefined,
        comment: comment.trim() || undefined,
      };
      await financeApi.createPayment(data);
      onSuccess();
    } catch (err: any) {
      setError('Ошибка: ' + (err?.response?.data?.detail || err.message));
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full">
        <div className="p-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-bold text-gray-900">💳 Принять оплату</h2>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl">×</button>
          </div>

          <div className="bg-blue-50 p-3 rounded mb-4 text-sm">
            <div className="flex justify-between">
              <span>Счёт:</span>
              <span className="font-semibold">{invoice.document_number}</span>
            </div>
            <div className="flex justify-between">
              <span>Сумма:</span>
              <span className="font-semibold">{formatMoney(total)}</span>
            </div>
            <div className="flex justify-between text-green-700">
              <span>Оплачено:</span>
              <span className="font-semibold">{formatMoney(paid)}</span>
            </div>
            <div className="flex justify-between text-orange-700 border-t border-blue-200 pt-1 mt-1">
              <span>К оплате:</span>
              <span className="font-bold">{formatMoney(remaining)}</span>
            </div>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded mb-4 text-sm">{error}</div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Сумма платежа *</label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-green-500 outline-none text-lg font-semibold"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Способ оплаты *</label>
              <select
                value={method}
                onChange={(e) => setMethod(e.target.value as PaymentMethod)}
                className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-green-500 outline-none"
              >
                {PAYMENT_METHODS.map((m) => (
                  <option key={m.value} value={m.value}>{m.label}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Дата платежа *</label>
              <input
                type="date"
                value={paymentDate}
                onChange={(e) => setPaymentDate(e.target.value)}
                className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-green-500 outline-none"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">ID транзакции</label>
              <input
                type="text"
                value={externalId}
                onChange={(e) => setExternalId(e.target.value)}
                className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-green-500 outline-none"
                placeholder="Например: TX-12345"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Комментарий</label>
              <textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                rows={2}
                className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-green-500 outline-none"
                placeholder="Примечание к платежу"
              />
            </div>

            <div className="flex justify-end space-x-3 pt-4 border-t">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 border border-gray-300 text-gray-700 rounded hover:bg-gray-50"
                disabled={saving}
              >
                Отмена
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
                disabled={saving}
              >
                {saving ? 'Регистрация...' : 'Принять оплату'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default PaymentModal;
