import React, { useState, useEffect } from 'react';
import type { Invoice, InvoiceCreate, InvoiceItemCreate } from '../api/finance';
import { requestsApi, type Request } from '../api/requests';
import { TaxSystemSelector } from './TaxSystemSelector';
import { companiesApi } from '../api/companies';
import { contractorsApi, type Contractor } from '../api/contractors';
import { useAuth } from '../contexts/AuthContext';

interface Props {
  invoice: Invoice | null;
  onClose: () => void;
  onSave: (data: InvoiceCreate) => Promise<void>;
}

interface ItemRow extends InvoiceItemCreate {
  key: string;
}

const toDateString = (iso: string | null | undefined) => {
  if (!iso) return new Date().toISOString().substring(0, 10);
  return iso.substring(0, 10);
};

export const InvoiceFormModal: React.FC<Props> = ({ invoice, onClose, onSave }) => {
  const { user } = useAuth();
  const [clientId, setClientId] = useState(invoice?.client_id?.toString() || '');
  const [invoiceDate, setInvoiceDate] = useState(toDateString(invoice?.invoice_date));
  const [dueDate, setDueDate] = useState(toDateString(invoice?.due_date));
  const [comment, setComment] = useState(invoice?.comment || '');

  const [taxSystem, setTaxSystem] = useState(invoice?.tax_system || 'osno');
  const [vatRate, setVatRate] = useState(invoice?.vat_rate?.toString() || '20');
  const [isVatIncluded, setIsVatIncluded] = useState(invoice?.is_vat_included ?? true);
  const [contractors, setContractors] = useState<Contractor[]>([]);
  const [searchContractor, setSearchContractor] = useState('');
  const [isManualTaxOverride, setIsManualTaxOverride] = useState(false);

  const [items, setItems] = useState<ItemRow[]>(
    invoice?.items?.length
      ? invoice.items.map((it, idx) => ({
          key: `item-${idx}`,
          description: it.description,
          quantity: typeof it.quantity === 'number' ? it.quantity : parseFloat(String(it.quantity)) || 0,
          unit_price: typeof it.unit_price === 'number' ? it.unit_price : parseFloat(String(it.unit_price)) || 0,
        }))
      : [{ key: 'item-0', description: '', quantity: 1, unit_price: 0 }],
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [requests, setRequests] = useState<Request[]>([]);
  const [requestId, setRequestId] = useState<string>(invoice?.request_id?.toString() || '');

  // Загрузка заявок
  useEffect(() => {
    requestsApi
      .getAll({ limit: 100 })
      .then((response: any) => {
        const data = response?.results || response?.data || response;
        if (Array.isArray(data)) {
          setRequests(data as Request[]);
        }
      })
      .catch((err) => {
        console.error('Ошибка загрузки заявок:', err);
      });
  }, []);

  // Загрузка клиентов
  useEffect(() => {
    contractorsApi
      .getAll({ type: 'client', is_active: true, limit: 500 })
      .then(setContractors)
      .catch((err) => {
        console.error('Ошибка загрузки клиентов:', err);
      });
  }, []);

  // АВТОЗАГРУЗКА настроек компании для НОВОГО счёта
  useEffect(() => {
    if (!invoice && user?.company_id && !isManualTaxOverride) {
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
  }, [invoice, user]);

  const updateItem = (key: string, field: keyof InvoiceItemCreate, value: any) => {
    setItems(items.map((it) => (it.key === key ? { ...it, [field]: value } : it)));
  };

  const addItem = () => {
    setItems([...items, { key: `item-${Date.now()}`, description: '', quantity: 1, unit_price: 0 }]);
  };

  const removeItem = (key: string) => {
    if (items.length === 1) return;
    setItems(items.filter((it) => it.key !== key));
  };

  const subtotal = items.reduce(
    (sum, it) => sum + (parseFloat(String(it.quantity)) || 0) * (parseFloat(String(it.unit_price)) || 0),
    0,
  );

  const isOsno = taxSystem === 'osno';
  const vatRateNum = isOsno ? parseFloat(vatRate || '0') : 0;

  let vat = 0;
  let total = subtotal;

  if (isOsno && vatRateNum > 0) {
    if (isVatIncluded) {
      vat = subtotal * vatRateNum / (100 + vatRateNum);
      total = subtotal;
    } else {
      vat = subtotal * vatRateNum / 100;
      total = subtotal + vat;
    }
  }

  const handleTaxSystemChange = (newSystem: string) => {
    setTaxSystem(newSystem);
    setIsManualTaxOverride(true);
    if (newSystem !== 'osno') {
      setVatRate('0');
    } else if (vatRate === '0') {
      setVatRate('20');
    }
  };

  // 🆕 Обработчик выбора клиента с автоподстановкой tax_system
  const handleContractorChange = (contractorId: string) => {
    setClientId(contractorId);
    setSearchContractor('');

    if (!contractorId) return;

    // Автоматически подставляем систему налогов клиента (только для новых счетов)
    if (!invoice && !isManualTaxOverride) {
      const contractor = contractors.find((c) => c.id === parseInt(contractorId));
      if (contractor?.tax_system) {
        setTaxSystem(contractor.tax_system);
        if (contractor.tax_system !== 'osno') {
          setVatRate('0');
        } else {
          setVatRate('20');
        }
      }
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!clientId) {
      setError('Укажите клиента');
      return;
    }
    if (!requestId) {
      setError('Укажите заявку');
      return;
    }
    if (!invoiceDate || !dueDate) {
      setError('Укажите даты');
      return;
    }
    if (items.length === 0 || items.every((it) => !it.description.trim())) {
      setError('Добавьте хотя бы одну позицию');
      return;
    }

    setSaving(true);
    try {
      await onSave({
        request_id: parseInt(requestId),
        client_id: parseInt(clientId),
        invoice_date: invoiceDate,
        due_date: dueDate,
        vat_rate: parseFloat(vatRate || '0'),
        comment: comment.trim() || undefined,
        tax_system: taxSystem,
        is_vat_included: isVatIncluded,
        items: items
          .filter((it) => it.description.trim())
          .map((it) => ({
            description: it.description.trim(),
            quantity: parseFloat(String(it.quantity)) || 0,
            unit_price: parseFloat(String(it.unit_price)) || 0,
          })),
      });
      setSaving(false);
    } catch (err) {
      setSaving(false);
    }
  };

  // Получаем выбранного клиента для превью
  const selectedContractor = clientId
    ? contractors.find((c) => c.id === parseInt(clientId))
    : null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold text-gray-900">
              {invoice ? `Редактировать ${invoice.document_number}` : 'Новый счёт'}
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
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
                      #{req.id} — {req.work_type} ({req.object_address})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Клиент *</label>
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
                  <option value="">— Выберите клиента —</option>
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

                {/* Превью реквизитов выбранного клиента */}
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
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Дата счёта *</label>
                <input
                  type="date"
                  value={invoiceDate}
                  onChange={(e) => setInvoiceDate(e.target.value)}
                  className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Срок оплаты *
                </label>
                <input
                  type="date"
                  value={dueDate}
                  onChange={(e) => setDueDate(e.target.value)}
                  className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                  required
                />
              </div>
            </div>

            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <TaxSystemSelector
                value={taxSystem}
                onChange={handleTaxSystemChange}
                onVatRateChange={(rate) => {
                  setVatRate(rate);
                  setIsManualTaxOverride(true);
                }}
              />

              {taxSystem === 'osno' && (
                <div className="mt-3 flex items-center">
                  <input
                    id="isVatIncluded"
                    type="checkbox"
                    checked={isVatIncluded}
                    onChange={(e) => {
                      setIsVatIncluded(e.target.checked);
                      setIsManualTaxOverride(true);
                    }}
                    className="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500"
                  />
                  <label htmlFor="isVatIncluded" className="ml-2 text-sm text-gray-700">
                    НДС включён в сумму позиции (иначе — начисляется сверху)
                  </label>
                </div>
              )}
            </div>

            <div>
              <div className="flex justify-between items-center mb-2">
                <label className="block text-sm font-medium text-gray-700">Позиции</label>
                <button
                  type="button"
                  onClick={addItem}
                  className="text-sm text-blue-600 hover:text-blue-900"
                >
                  + Добавить позицию
                </button>
              </div>

              <div className="space-y-2">
                <div className="grid grid-cols-12 gap-2 text-xs font-medium text-gray-500 px-2">
                  <div className="col-span-6">Описание</div>
                  <div className="col-span-2">Кол-во</div>
                  <div className="col-span-2">Цена</div>
                  <div className="col-span-2 text-right">Сумма</div>
                </div>
                {items.map((it) => {
                  const amount =
                    (parseFloat(String(it.quantity)) || 0) *
                    (parseFloat(String(it.unit_price)) || 0);
                  return (
                    <div key={it.key} className="grid grid-cols-12 gap-2 items-center">
                      <input
                        type="text"
                        value={it.description}
                        onChange={(e) => updateItem(it.key, 'description', e.target.value)}
                        placeholder="Например: Аренда экскаватора"
                        className="col-span-6 p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                      />
                      <input
                        type="number"
                        step="0.1"
                        min="0"
                        value={it.quantity}
                        onChange={(e) => updateItem(it.key, 'quantity', e.target.value)}
                        className="col-span-2 p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                      />
                      <input
                        type="number"
                        step="100"
                        min="0"
                        value={it.unit_price}
                        onChange={(e) => updateItem(it.key, 'unit_price', e.target.value)}
                        className="col-span-2 p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                      />
                      <div className="col-span-1 text-right text-sm font-medium text-gray-900">
                        {amount.toLocaleString('ru-RU')} ₽
                      </div>
                      <div className="col-span-1 text-right">
                        <button
                          type="button"
                          onClick={() => removeItem(it.key)}
                          className="text-red-600 hover:text-red-900 text-lg"
                          disabled={items.length === 1}
                        >
                          ×
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="bg-gray-50 p-4 rounded-lg space-y-1">
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Сумма без НДС:</span>
                <span className="font-medium">
                  {subtotal.toLocaleString('ru-RU', { minimumFractionDigits: 2 })} ₽
                </span>
              </div>

              {isOsno ? (
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">
                    НДС ({vatRate}%)
                    {isVatIncluded && <span className="text-xs text-gray-500"> — включён</span>}
                    {!isVatIncluded && <span className="text-xs text-gray-500"> — сверху</span>} :
                  </span>
                  <span className="font-medium">
                    {vat.toLocaleString('ru-RU', { minimumFractionDigits: 2 })} ₽
                  </span>
                </div>
              ) : (
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">НДС:</span>
                  <span className="font-medium text-blue-600">
                    Без НДС
                    {taxSystem === 'usn_6' && ' (УСН "Доходы")'}
                    {taxSystem === 'usn_15' && ' (УСН "Доходы-Расходы")'}
                    {taxSystem === 'patent' && ' (Патент)'}
                    {taxSystem === 'npd' && ' (НПД)'}
                  </span>
                </div>
              )}

              <div className="flex justify-between text-base pt-2 border-t border-gray-300">
                <span className="font-semibold text-gray-900">ИТОГО:</span>
                <span className="font-bold text-lg text-blue-600">
                  {total.toLocaleString('ru-RU', { minimumFractionDigits: 2 })} ₽
                </span>
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
                {saving ? 'Сохранение...' : invoice ? 'Сохранить' : 'Создать счёт'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default InvoiceFormModal;
