import React, { useState, useEffect } from 'react';
import { requestsApi, type Request } from '../api/requests';
import type { Act, ActCreate } from '../api/finance';

interface Props {
  act: Act | null;
  initialRequestId?: number | null;
  onClose: () => void;
  onSave: (data: ActCreate) => Promise<void>;
}

const toDateString = (iso: string | null | undefined) => {
  if (!iso) return new Date().toISOString().substring(0, 10);
  return iso.substring(0, 10);
};

export const ActFormModal: React.FC<Props> = ({ act, initialRequestId, onClose, onSave }) => {
  const [requests, setRequests] = useState<Request[]>([]);
  const [requestId, setRequestId] = useState<string>(
    act?.request_id?.toString() || initialRequestId?.toString() || ''
  );
  const [clientId, setClientId] = useState(act?.client_id?.toString() || '1');
  const [totalAmount, setTotalAmount] = useState(act?.total_amount || '');
  const [actDate, setActDate] = useState(toDateString(act?.act_date));
  const [comment, setComment] = useState(act?.comment || '');
  const [userEditedAmount, setUserEditedAmount] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    requestsApi.getAll({ limit: 500 })
      .then(setRequests)
      .catch(() => setRequests([]));
  }, []);

  // ✅ Автозаполнение суммы при смене заявки (только в режиме создания и если пользователь не редактировал вручную)
  useEffect(() => {
    if (requestId && !act && !userEditedAmount) {
      const req = requests.find((r) => r.id === parseInt(requestId));
      if (req?.estimated_amount) {
        setTotalAmount(req.estimated_amount.toString());
      }
    }
  }, [requestId, requests, act, userEditedAmount]);

  const handleAmountChange = (value: string) => {
    setTotalAmount(value);
    setUserEditedAmount(true); // Пользователь начал редактировать вручную
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!requestId) { setError('Выберите заявку'); return; }
    if (!clientId) { setError('Укажите клиента'); return; }
    if (!totalAmount || parseFloat(totalAmount) <= 0) { setError('Укажите сумму'); return; }

    setSaving(true);
    try {
      await onSave({
        request_id: parseInt(requestId),
        client_id: parseInt(clientId),
        total_amount: parseFloat(totalAmount),
        act_date: actDate,
        comment: comment.trim() || undefined,
      });
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (Array.isArray(detail)) {
        setError('Ошибка валидации: ' + detail.map((d: any) => `${d.loc?.join('.')}: ${d.msg}`).join(', '));
      } else {
        setError('Ошибка: ' + (detail || err.message));
      }
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full">
        <div className="p-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold text-gray-900">
              {act ? `Редактировать ${act.document_number}` : 'Новый акт'}
            </h2>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl">×</button>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">{error}</div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Заявка *</label>
              <select
                value={requestId}
                onChange={(e) => setRequestId(e.target.value)}
                className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                required
              >
                <option value="">— Выберите заявку —</option>
                {requests.map((req) => (
                  <option key={req.id} value={req.id}>
                    #{req.id} — {req.work_type} ({req.object_address}) — {req.estimated_amount} ₽
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Клиент ID *</label>
                <input
                  type="number"
                  value={clientId}
                  onChange={(e) => setClientId(e.target.value)}
                  className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Сумма (₽) *</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={totalAmount}
                  onChange={(e) => handleAmountChange(e.target.value)}
                  className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Дата акта *</label>
                <input
                  type="date"
                  value={actDate}
                  onChange={(e) => setActDate(e.target.value)}
                  className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Комментарий</label>
              <textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                rows={2}
                className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                placeholder="Дополнительная информация"
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
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                disabled={saving}
              >
                {saving ? 'Сохранение...' : (act ? 'Сохранить' : 'Создать акт')}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default ActFormModal;
