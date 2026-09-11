import React, { useState } from 'react';
import type {
  Request,
  RequestCreate,
  RequestStatus,
  RequestType,
  RateType,
  SourceChannel,
  Priority,
} from '../api/requests';

interface Props {
  request: Request | null;
  onClose: () => void;
  onSave: (data: RequestCreate) => Promise<void>;
}

const REQUEST_TYPES: { value: RequestType; label: string }[] = [
  { value: 'one_time', label: 'Разовая' },
  { value: 'recurring', label: 'Повторяющаяся' },
];

const RATE_TYPES: { value: RateType; label: string }[] = [
  { value: 'hourly', label: 'Почасовая' },
  { value: 'daily', label: 'Посменная' },
  { value: 'shift', label: 'За смену' },
  { value: 'fixed', label: 'Фиксированная' },
];

const SOURCE_CHANNELS: { value: SourceChannel; label: string }[] = [
  { value: 'phone', label: 'Телефон' },
  { value: 'web', label: 'Сайт' },
  { value: 'mobile', label: 'Мобильное приложение' },
  { value: 'email', label: 'Email' },
];

const PRIORITIES: { value: Priority; label: string }[] = [
  { value: 'low', label: 'Низкий' },
  { value: 'normal', label: 'Обычный' },
  { value: 'high', label: 'Высокий' },
  { value: 'urgent', label: 'Срочный' },
];

const STATUSES: { value: RequestStatus; label: string }[] = [
  { value: 'new', label: 'Новая' },
  { value: 'processing', label: 'В обработке' },
  { value: 'assigned', label: 'Назначена' },
  { value: 'confirmed', label: 'Подтверждена' },
  { value: 'released', label: 'Выпущена' },
  { value: 'in_progress', label: 'В работе' },
  { value: 'completed', label: 'Завершена' },
  { value: 'signed', label: 'Подписана' },
  { value: 'closed', label: 'Закрыта' },
  { value: 'cancelled', label: 'Отменена' },
  { value: 'disputed', label: 'Спорная' },
];

const toLocalDatetime = (iso: string | null | undefined) => {
  if (!iso) return '';
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

export const RequestFormModal: React.FC<Props> = ({ request, onClose, onSave }) => {
  const [workType, setWorkType] = useState(request?.work_type || '');
  const [objectAddress, setObjectAddress] = useState(request?.object_address || '');
  const [requestType, setRequestType] = useState<RequestType>(request?.request_type || 'one_time');
  const [plannedStart, setPlannedStart] = useState(toLocalDatetime(request?.planned_start));
  const [plannedEnd, setPlannedEnd] = useState(toLocalDatetime(request?.planned_end));
  const [shiftDuration, setShiftDuration] = useState(request?.shift_duration_hours?.toString() || '');
  const [clientRate, setClientRate] = useState(request?.client_rate?.toString() || '');
  const [rateType, setRateType] = useState<RateType>((request?.rate_type as RateType) || 'hourly');
  const [estimatedAmount, setEstimatedAmount] = useState(request?.estimated_amount?.toString() || '');
  const [sourceChannel, setSourceChannel] = useState<SourceChannel>((request?.source_channel as SourceChannel) || 'phone');
  const [priority, setPriority] = useState<Priority>((request?.priority as Priority) || 'normal');
  const [status, setStatus] = useState<RequestStatus>(request?.status || 'new');
  const [comment, setComment] = useState(request?.comment || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!workType.trim()) {
      setError('Введите тип работы');
      return;
    }
    if (!objectAddress.trim()) {
      setError('Введите адрес объекта');
      return;
    }
    if (!plannedStart || !plannedEnd) {
      setError('Укажите даты начала и окончания');
      return;
    }

    setSaving(true);
    try {
      const payload: any = {
        work_type: workType.trim(),
        object_address: objectAddress.trim(),
        request_type: requestType,
        planned_start: new Date(plannedStart).toISOString(),
        planned_end: new Date(plannedEnd).toISOString(),
        rate_type: rateType,
        source_channel: sourceChannel,
        priority: priority,
        comment: comment.trim() || undefined,
      };

      if (shiftDuration) payload.shift_duration_hours = parseFloat(shiftDuration);
      if (clientRate) payload.client_rate = parseFloat(clientRate);
      if (estimatedAmount) payload.estimated_amount = parseFloat(estimatedAmount);

      if (request) {
        payload.status = status;
      }

      await onSave(payload);
    } catch (err) {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold text-gray-900">
              {request ? `Редактировать заявку #${request.id}` : 'Новая заявка'}
            </h2>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl">×</button>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Тип заявки *</label>
                <select
                  value={requestType}
                  onChange={(e) => setRequestType(e.target.value as RequestType)}
                  className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                >
                  {REQUEST_TYPES.map(t => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Приоритет *</label>
                <select
                  value={priority}
                  onChange={(e) => setPriority(e.target.value as Priority)}
                  className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                >
                  {PRIORITIES.map(p => (
                    <option key={p.value} value={p.value}>{p.label}</option>
                  ))}
                </select>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Тип работы *</label>
              <input
                type="text"
                value={workType}
                onChange={(e) => setWorkType(e.target.value)}
                className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                placeholder="Например: Земляные работы"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Адрес объекта *</label>
              <input
                type="text"
                value={objectAddress}
                onChange={(e) => setObjectAddress(e.target.value)}
                className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                placeholder="Например: Москва, Красная площадь"
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Плановое начало *</label>
                <input
                  type="datetime-local"
                  value={plannedStart}
                  onChange={(e) => setPlannedStart(e.target.value)}
                  className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Плановое окончание *</label>
                <input
                  type="datetime-local"
                  value={plannedEnd}
                  onChange={(e) => setPlannedEnd(e.target.value)}
                  className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                  required
                />
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Длительность смены (ч)</label>
                <input
                  type="number"
                  step="0.5"
                  min="0"
                  value={shiftDuration}
                  onChange={(e) => setShiftDuration(e.target.value)}
                  className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                  placeholder="8"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Ставка клиента</label>
                <input
                  type="number"
                  step="100"
                  min="0"
                  value={clientRate}
                  onChange={(e) => setClientRate(e.target.value)}
                  className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                  placeholder="5000"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Тип ставки</label>
                <select
                  value={rateType}
                  onChange={(e) => setRateType(e.target.value as RateType)}
                  className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                >
                  {RATE_TYPES.map(r => (
                    <option key={r.value} value={r.value}>{r.label}</option>
                  ))}
                </select>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Ожидаемая сумма (₽)</label>
              <input
                type="number"
                step="100"
                min="0"
                value={estimatedAmount}
                onChange={(e) => setEstimatedAmount(e.target.value)}
                className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                placeholder="40000"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Источник заявки</label>
                <select
                  value={sourceChannel}
                  onChange={(e) => setSourceChannel(e.target.value as SourceChannel)}
                  className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                >
                  {SOURCE_CHANNELS.map(s => (
                    <option key={s.value} value={s.value}>{s.label}</option>
                  ))}
                </select>
              </div>
              {request && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Статус</label>
                  <select
                    value={status}
                    onChange={(e) => setStatus(e.target.value as RequestStatus)}
                    className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                  >
                    {STATUSES.map(s => (
                      <option key={s.value} value={s.value}>{s.label}</option>
                    ))}
                  </select>
                </div>
              )}
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
                {saving ? 'Сохранение...' : (request ? 'Сохранить' : 'Создать')}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default RequestFormModal;
