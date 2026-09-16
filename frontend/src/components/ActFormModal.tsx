import React, { useState, useEffect } from 'react';
import { requestsApi, type Request } from '../api/requests';
import { contractorsApi, type Contractor } from '../api/contractors';
import { companiesApi } from '../api/companies';
import { TaxSystemSelector } from './TaxSystemSelector';
import type { Act, ActCreate } from '../api/finance';
import { useAuth } from '../contexts/AuthContext';

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
  const { user } = useAuth();
  const [requests, setRequests] = useState<Request[]>([]);
  const [contractors, setContractors] = useState<Contractor[]>([]);
  const [searchContractor, setSearchContractor] = useState('');
  const [isManualTaxOverride, setIsManualTaxOverride] = useState(false);

  const [requestId, setRequestId] = useState<string>(
    act?.request_id?.toString() || initialRequestId?.toString() || '',
  );
  const [clientId, setClientId] = useState(act?.client_id?.toString() || '');
  const [totalAmount, setTotalAmount] = useState(act?.total_amount || '');
  const [actDate, setActDate] = useState(toDateString(act?.act_date));
  const [comment, setComment] = useState(act?.comment || '');
  const [userEditedAmount, setUserEditedAmount] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  // Налоги
  const [taxSystem, setTaxSystem] = useState(act?.tax_system || 'osno');
  const [vatRate, setVatRate] = useState(act?.vat_rate?.toString() || '20');
  const [isVatIncluded, setIsVatIncluded] = useState(act?.is_vat_included ?? true);

  useEffect(() => {
    requestsApi
      .getAll({ limit: 500 })
      .then(setRequests)
      .catch(() => setRequests([]));

    contractorsApi
      .getAll({ type: 'client', is_active: true, limit: 500 })
      .then(setContractors)
      .catch(() => setContractors([]));
  }, []);

  // Автозаполнение суммы при смене заявки
  useEffect(() => {
    if (requestId && !act && !userEditedAmount) {
      const req = requests.find((r) => r.id === parseInt(requestId));
      if (req?.estimated_amount) {
        setTotalAmount(req.estimated_amount.toString());
      }
      // Автозаполнение клиента из заявки
      if ((req as any)?.client_id) {
        setClientId((req as any).client_id.toString());
      }
    }
  }, [requestId, requests, act, userEditedAmount]);

  // АВТОЗАГРУЗКА настроек компании
  useEffect(() => {
    if (!act && user?.company_id && !isManualTaxOverride) {
      companiesApi
        .getTaxSettings(user.company_id)
        .then((settings) => {
          setTaxSystem(settings.default_tax_system);
          setVatRate(settings.default_vat_rate.toString());
          setIsVatIncluded(settings.default_is_vat_included);
        })
        .catch((err) => {
          console.warn('Не удалось загрузить настройки компании:', err);
        });
    }
  }, [act, user]);

  const handleAmountChange = (value: string) => {
    setTotalAmount(value);
    setUserEditedAmount(true);
  };

  const handleTaxSystemChange = (newSystem: string) => {
    setIsManualTaxOverride(true);
    setTaxSystem(newSystem);
    if (newSystem !== 'osno') {
      setVatRate('0');
    } else if (vatRate === '0') {
      setVatRate('20');
    }
  };

  // Выбор клиента с автоподстановкой системы налогов
  const handleContractorChange = (contractorId: string) => {
    setClientId(contractorId);
    setSearchContractor('');

    if (!contractorId || act || isManualTaxOverride) return;

    const contractor = contractors.find((c) => c.id === parseInt(contractorId));
    if (contractor?.tax_system) {
      setTaxSystem(contractor.tax_system);
      setVatRate(contractor.tax_system !== 'osno' ? '0' : '20');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!requestId) {
      setError('Выберите заявку');
      return;
    }
    if (!clientId) {
      setError('Выберите заказчика');
      return;
    }
    if (!totalAmount || parseFloat(totalAmount) <= 0) {
      setError('Укажите сумму');
      return;
    }

    setSaving(true);
    try {
      await onSave({
        request_id: parseInt(requestId),
        client_id: parseInt(clientId),
        total_amount: parseFloat(totalAmount),
        act_date: actDate,
        comment: comment.trim() || undefined,
        tax_system: taxSystem,
        vat_rate: parseFloat(vatRate || '0'),
        is_vat_included: isVatIncluded,
      });
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (Array.isArray(detail)) {
        setError(
          'Ошибка валидации: ' + detail.map((d: any) => `${d.loc?.join('.')}: ${d.msg}`).join(', '),
        );
      } else {
        setError('Ошибка: ' + (detail || err.message));
      }
      setSaving(false);
    }
  };

  const selectedContractor = clientId
    ? contractors.find((c) => c.id === parseInt(clientId))
    : null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold text-gray-900">
              {act ? `Редактировать ${act.document_number}` : 'Новый акт'}
            </h2>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl">
              ×
            </button>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
              {error}
            </div>
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

            {/* 🆕 Блок выбора заказчика */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                👤 Заказчик *
              </label>
              <input
                type="text"
                placeholder="Поиск по названию или ИНН..."
                value={searchContractor}
                onChange={(e) => setSearchContractor(e.target.value)}
                className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none mb-2"
              />
              <select
                value={clientId}
                onChange={(e) => handleContractorChange(e.target.value)}
                className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                required
              >
                <option value="">— Выберите заказчика —</option>
                {contractors
                  .filter(
                    (c) =>
                      !searchContractor ||
                      c.name.toLowerCase().includes(searchContractor.toLowerCase()) ||
                      c.inn?.toLowerCase().includes(searchContractor.toLowerCase()),
                  )
                  .map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} {c.inn ? `(ИНН: ${c.inn})` : ''}
                    </option>
                  ))}
              </select>

              {selectedContractor && (
                <div className="mt-2 p-3 bg-blue-50 border border-blue-200 rounded text-xs text-blue-900">
                  <div className="font-semibold mb-1">{selectedContractor.name}</div>
                  {selectedContractor.inn && (
                    <div>
                      ИНН: {selectedContractor.inn}
                      {selectedContractor.kpp ? ` / КПП: ${selectedContractor.kpp}` : ''}
                    </div>
                  )}
                  {selectedContractor.legal_address && (
                    <div className="truncate">Адрес: {selectedContractor.legal_address}</div>
                  )}
                  {selectedContractor.tax_system && (
                    <div>
                      Система налогов:{' '}
                      <span className="font-medium">
                        {selectedContractor.tax_system === 'osno' && 'ОСНО'}
                        {selectedContractor.tax_system === 'usn_6' && 'УСН "Доходы"'}
                        {selectedContractor.tax_system === 'usn_15' && 'УСН "Доходы-Расходы"'}
                        {selectedContractor.tax_system === 'patent' && 'Патент'}
                        {selectedContractor.tax_system === 'npd' && 'НПД'}
                      </span>
                    </div>
                  )}
                </div>
              )}

              <button
                type="button"
                onClick={() => window.open('/contractors', '_blank')}
                className="mt-2 text-xs text-blue-600 hover:text-blue-800"
              >
                + Добавить нового клиента
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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

            {/* Блок налогов */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <TaxSystemSelector
                value={taxSystem}
                onChange={handleTaxSystemChange}
                onVatRateChange={(rate) => {
                  setIsManualTaxOverride(true);
                  setVatRate(rate);
                }}
              />

              {taxSystem === 'osno' && (
                <div className="mt-3 flex items-center">
                  <input
                    id="actVatIncludedModal"
                    type="checkbox"
                    checked={isVatIncluded}
                    onChange={(e) => {
                      setIsManualTaxOverride(true);
                      setIsVatIncluded(e.target.checked);
                    }}
                    className="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500"
                  />
                  <label htmlFor="actVatIncludedModal" className="ml-2 text-sm text-gray-700">
                    НДС включён в сумму (иначе — начисляется сверху)
                  </label>
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
                {saving ? 'Сохранение...' : act ? 'Сохранить' : 'Создать акт'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default ActFormModal;
