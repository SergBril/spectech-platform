import React, { useState, useEffect } from 'react';
import type {
  Request,
  RequestCreate,
  RequestStatus,
  RequestType,
  RateType,
  SourceChannel,
  Priority,
} from '../api/requests';
import apiClient from '../api/client';
import { requestsApi } from '../api/requests';
import AddressAutocomplete from './AddressAutocomplete';
import { getCatalogTree, getSubcategoryAttributes, addCustomOption, type CategoryTree, type AttributeDefinition } from '../api/catalog';

interface Contractor {
  id: number;
  name: string;
  type: string;
}

interface Props {
  request: Request | null;
  onClose: () => void;
  onSave: (data: RequestCreate) => Promise<void>;
  vehicleId?: number;
  vehicleName?: string;
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

export const RequestFormModal: React.FC<Props> = ({
  request,
  onClose,
  onSave,
  vehicleId,
  vehicleName,
}) => {
  const [workType, setWorkType] = useState(request?.work_type || '');
  const [objectAddress, setObjectAddress] = useState(request?.object_address || '');
  const [requestType, setRequestType] = useState<RequestType>(request?.request_type || 'one_time');
  const [plannedStart, setPlannedStart] = useState(toLocalDatetime(request?.planned_start));
  const [plannedEnd, setPlannedEnd] = useState(toLocalDatetime(request?.planned_end));
  const [shiftDuration, setShiftDuration] = useState(request?.shift_duration_hours?.toString() || '8');
  const [clientRate, setClientRate] = useState(request?.client_rate?.toString() || '');
  const [rateType, setRateType] = useState<RateType>((request?.rate_type as RateType) || 'hourly');
  const [estimatedAmount, setEstimatedAmount] = useState(request?.estimated_amount?.toString() || '');
  const [sourceChannel, setSourceChannel] = useState<SourceChannel>((request?.source_channel as SourceChannel) || (vehicleId ? 'web' : 'phone'));
  const [priority, setPriority] = useState<Priority>((request?.priority as Priority) || 'normal');
  const [status, setStatus] = useState<RequestStatus>(request?.status || 'new');
  const [comment, setComment] = useState(request?.comment || '');
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [error, setError] = useState('');

  // Выбор клиента
  const [clients, setClients] = useState<Contractor[]>([]);
  const [selectedClientId, setSelectedClientId] = useState<number | null>(request?.client_id || null);
  const [loadingClients, setLoadingClients] = useState(true);

  // Категория и подкатегория
  const [catalogTree, setCatalogTree] = useState<CategoryTree[]>([]);
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(null);
  const [selectedSubcategoryId, setSelectedSubcategoryId] = useState<number | null>(request?.vehicle_category_id || null);
  const [subcategoryAttributes, setSubcategoryAttributes] = useState<AttributeDefinition[]>([]);
  const [attributeValues, setAttributeValues] = useState<Record<string, string>>({});
  const [loadingAttributes, setLoadingAttributes] = useState(false);

  // Назначение: свой водитель или маркетплейс
  const [assignmentMode, setAssignmentMode] = useState<'own' | 'marketplace'>('own');
  const [marketplaceMode, setMarketplaceMode] = useState<'client' | 'owner_dispatcher'>('client');
  const [paymentTermsDays, setPaymentTermsDays] = useState<number>(7);
  const [showExtendedPaymentWarning, setShowExtendedPaymentWarning] = useState(false);
  const [drivers, setDrivers] = useState<{id: number; name: string}[]>([]);
  const [selectedDriverId, setSelectedDriverId] = useState<number | null>(null);
  const [loadingDrivers, setLoadingDrivers] = useState(false);

  // Custom attribute value modal
  const [customAttrModal, setCustomAttrModal] = useState<{ attrId: number; attrName: string; slug: string } | null>(null);
  const [customValue, setCustomValue] = useState('');
  const [customNumericValue, setCustomNumericValue] = useState('');
  const [addingCustom, setAddingCustom] = useState(false);
  const [customError, setCustomError] = useState('');

  // Загрузка клиентов, каталога и водителей
  useEffect(() => {
    const loadData = async () => {
      // Клиенты
      try {
        const res = await apiClient.get('/contractors', { params: { type: 'client', limit: 500 } });
        const list = Array.isArray(res.data) ? res.data : [];
        setClients(list);
        // Only set default client for new requests, not when editing
        if (!request && !selectedClientId && list.length > 0) setSelectedClientId(list[0].id);
      } catch (e) { console.warn('Failed to load clients:', e); }
      setLoadingClients(false);

      // Каталог
      try {
        const tree = await getCatalogTree();
        console.log('[RequestForm] Catalog tree loaded:', tree.length, 'categories');
        setCatalogTree(tree);
      } catch (e) { console.warn('Failed to load catalog:', e); }

      // Водители
      try {
        setLoadingDrivers(true);
        const res = await apiClient.get('/drivers', { params: { limit: 500 } });
        const list = Array.isArray(res.data) ? res.data : [];
        setDrivers(list.map((d: any) => ({ id: d.id, name: d.name || d.full_name || `Водитель #${d.id}` })));
      } catch (e) { console.warn('Failed to load drivers:', e); }
      setLoadingDrivers(false);
    };
    loadData();
  }, []);

  // При редактировании: определяем категорию по подкатегории
  useEffect(() => {
    if (request?.vehicle_category_id && catalogTree.length > 0 && !selectedCategoryId) {
      for (const cat of catalogTree) {
        const sub = cat.subcategories.find(s => s.id === request.vehicle_category_id);
        if (sub) {
          setSelectedCategoryId(cat.id);
          setSelectedSubcategoryId(sub.id);
          break;
        }
      }
    }
  }, [request, catalogTree]);

  // Загрузка атрибутов при выборе подкатегории
  useEffect(() => {
    if (selectedSubcategoryId) {
      setLoadingAttributes(true);
      getSubcategoryAttributes(selectedSubcategoryId)
        .then(attrs => {
          console.log('[RequestForm] Attributes loaded:', attrs.length);
          setSubcategoryAttributes(attrs);
        })
        .catch((e) => { console.warn('Failed to load attributes:', e); setSubcategoryAttributes([]); })
        .finally(() => setLoadingAttributes(false));
    } else {
      setSubcategoryAttributes([]);
    }
  }, [selectedSubcategoryId]);



  // 🆕 АВТО-РАСЧЁТ суммы: часы × ставка
  useEffect(() => {
    const hours = parseFloat(shiftDuration) || 0;
    const rate = parseFloat(clientRate) || 0;

    if (hours > 0 && rate > 0 && !request) {
      let total = 0;

      switch (rateType) {
        case 'hourly':
          total = hours * rate;
          break;
        case 'daily':
        case 'shift':
          // Смена = 8 часов по умолчанию
          total = rate;
          break;
        case 'fixed':
          total = rate;
          break;
      }

      if (total > 0) {
        setEstimatedAmount(total.toString());
      }
    }
  }, [shiftDuration, clientRate, rateType, request]);

  // Если передано vehicleId — подставляем ставку техники как дефолт
  useEffect(() => {
    if (vehicleId && !request && !clientRate) {
      // Загружаем информацию о технике для автозаполнения ставки
      apiClient.get(`/public/vehicles/${vehicleId}`)
        .then(res => {
          const vehicle = res.data;
          if (vehicle.hourly_rate && !clientRate) {
            setClientRate(vehicle.hourly_rate.toString());
            setRateType('hourly');
          } else if (vehicle.shift_rate && !clientRate) {
            setClientRate(vehicle.shift_rate.toString());
            setRateType('shift');
          }
        })
        .catch(() => {});
    }
  }, [vehicleId]);

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

    if (!selectedClientId) {
      setError('Выберите клиента');
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
        source_channel: assignmentMode === 'marketplace' ? 'marketplace' : sourceChannel,
        marketplace_mode: assignmentMode === 'marketplace' ? marketplaceMode : undefined,
        payment_terms_days: assignmentMode === 'marketplace' ? paymentTermsDays : undefined,
        priority: priority,
        comment: comment.trim() || undefined,
        client_id: selectedClientId,
        vehicle_category_id: selectedSubcategoryId || undefined,
      };

      // 🆕 Добавляем vehicle_id для заявок с маркетплейса
      if (vehicleId) {
        payload.vehicle_id = vehicleId;
      }

      if (shiftDuration) payload.shift_duration_hours = parseFloat(shiftDuration);
      if (clientRate) payload.client_rate = parseFloat(clientRate);
      if (estimatedAmount) payload.estimated_amount = parseFloat(estimatedAmount);

      if (request) {
        payload.status = status;
      }

      await onSave(payload);
    } catch (err: any) {
      setSaving(false);
      const msg = err.response?.data?.detail || err.response?.data?.message || 'Ошибка при сохранении';
      setError(msg);
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

          {/* 🆕 Выбранная техника */}
          {vehicleId && vehicleName && (
            <div className="mb-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <p className="text-xs text-blue-600 uppercase font-semibold mb-1">Выбранная техника</p>
              <p className="text-lg font-bold text-gray-900">🚜 {vehicleName}</p>
            </div>
          )}



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

            {/* === КЛИЕНТ === */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Клиент *</label>
              <select
                value={selectedClientId ?? ''}
                onChange={(e) => setSelectedClientId(Number(e.target.value) || null)}
                className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                disabled={loadingClients}
              >
                <option value="">Выберите клиента</option>
                {clients.map(cl => (
                  <option key={cl.id} value={cl.id}>{cl.name}</option>
                ))}
              </select>
            </div>

            {/* === КАТЕГОРИЯ И ПОДКАТЕГОРИЯ === */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Категория техники</label>
                <select
                  value={selectedCategoryId ?? ''}
                  onChange={(e) => {
                    const catId = Number(e.target.value) || null;
                    setSelectedCategoryId(catId);
                    setSelectedSubcategoryId(null);
                    setAttributeValues({});
                  }}
                  className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                >
                  <option value="">Выберите категорию</option>
                  {catalogTree.map(cat => (
                    <option key={cat.id} value={cat.id}>{cat.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Подкатегория</label>
                <select
                  value={selectedSubcategoryId ?? ''}
                  onChange={(e) => {
                    setSelectedSubcategoryId(Number(e.target.value) || null);
                    setAttributeValues({});
                  }}
                  className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                  disabled={!selectedCategoryId}
                >
                  <option value="">Выберите подкатегорию</option>
                  {(catalogTree.find(c => c.id === selectedCategoryId)?.subcategories || []).map(sub => (
                    <option key={sub.id} value={sub.id}>{sub.name}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* === АТРИБУТЫ ПОДКАТЕГОРИИ === */}
            {subcategoryAttributes.length > 0 && (
              <div className="p-4 bg-gray-50 rounded-lg space-y-3">
                <p className="text-xs font-semibold text-gray-500 uppercase">Характеристики техники</p>
                <div className="grid grid-cols-2 gap-3">
                  {subcategoryAttributes.map(attr => (
                    <div key={attr.id}>
                      <label className="block text-xs font-medium text-gray-600 mb-1">
                        {attr.name} {attr.is_required && '*'}
                        {attr.unit && <span className="text-gray-400"> ({attr.unit})</span>}
                      </label>
                      {attr.data_type === 'select' ? (
                        <div className="flex gap-1">
                          <select
                            value={attributeValues[attr.slug] || ''}
                            onChange={(e) => setAttributeValues(prev => ({ ...prev, [attr.slug]: e.target.value }))}
                            className="flex-1 p-1.5 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                          >
                            <option value="">Выберите</option>
                            {attr.options.map(opt => (
                              <option key={opt.id} value={opt.value}>{opt.value}</option>
                            ))}
                          </select>
                          {attr.allow_custom_values && (
                            <button
                              type="button"
                              onClick={() => {
                                setCustomAttrModal({ attrId: attr.id, attrName: attr.name, slug: attr.slug });
                                setCustomValue('');
                                setCustomNumericValue('');
                                setCustomError('');
                              }}
                              className="px-2 py-1 bg-blue-100 text-blue-700 rounded hover:bg-blue-200 text-sm font-bold transition-colors"
                              title="Добавить новое значение"
                            >+</button>
                          )}
                        </div>
                      ) : (
                        <input
                          type={attr.data_type === 'number' ? 'number' : 'text'}
                          value={attributeValues[attr.slug] || ''}
                          onChange={(e) => setAttributeValues(prev => ({ ...prev, [attr.slug]: e.target.value }))}
                          className="w-full p-1.5 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                          placeholder={attr.data_type === 'number' ? '0' : ''}
                        />
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* === НАЗНАЧЕНИЕ: СВОЙ ВОДИТЕЛЬ ИЛИ МАРКЕТПЛЕЙС === */}
            {!request && (
              <div className="p-4 border border-gray-200 rounded-lg">
                <label className="block text-sm font-semibold text-gray-700 mb-3">Назначение заявки</label>
                <div className="flex gap-4 mb-3">
                  <label className={`flex items-center gap-2 cursor-pointer px-4 py-2 rounded-lg border transition-all ${
                    assignmentMode === 'own' ? 'border-blue-500 bg-blue-50 text-blue-700' : 'border-gray-200 hover:bg-gray-50'
                  }`}>
                    <input
                      type="radio"
                      name="assignmentMode"
                      value="own"
                      checked={assignmentMode === 'own'}
                      onChange={() => setAssignmentMode('own')}
                      className="accent-blue-600"
                    />
                    <span className="text-sm font-medium">👷 Свой водитель</span>
                  </label>
                  <label className={`flex items-center gap-2 cursor-pointer px-4 py-2 rounded-lg border transition-all ${
                    assignmentMode === 'marketplace' ? 'border-green-500 bg-green-50 text-green-700' : 'border-gray-200 hover:bg-gray-50'
                  }`}>
                    <input
                      type="radio"
                      name="assignmentMode"
                      value="marketplace"
                      checked={assignmentMode === 'marketplace'}
                      onChange={() => setAssignmentMode('marketplace')}
                      className="accent-green-600"
                    />
                    <span className="text-sm font-medium">🌐 Маркетплейс</span>
                  </label>
                </div>
                {assignmentMode === 'own' && (
                  <select
                    value={selectedDriverId ?? ''}
                    onChange={(e) => setSelectedDriverId(Number(e.target.value) || null)}
                    className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                    disabled={loadingDrivers}
                  >
                    <option value="">Выберите водителя</option>
                    {drivers.map(d => (
                      <option key={d.id} value={d.id}>{d.name}</option>
                    ))}
                  </select>
                )}
                {assignmentMode === 'marketplace' && (
                  <div className="space-y-3 bg-green-50 p-4 rounded border border-green-200">
                    <p className="text-sm text-green-700 font-medium">
                      📢 Заявка будет опубликована в маркетплейсе
                    </p>

                    {/* Режим маркетплейса */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Режим размещения *</label>
                      <div className="flex gap-3">
                        <label className={`flex-1 flex items-center gap-2 p-3 rounded border cursor-pointer transition-colors ${
                          marketplaceMode === 'client' ? 'border-purple-500 bg-purple-50 text-purple-700' : 'border-gray-200 hover:bg-gray-50'
                        }`}>
                          <input type="radio" name="mpMode" value="client"
                            checked={marketplaceMode === 'client'}
                            onChange={() => setMarketplaceMode('client')}
                            className="accent-purple-600" />
                          <div>
                            <div className="text-sm font-medium">🏪 Я заказчик</div>
                            <div className="text-xs text-gray-500">Плачу 100%, исполнитель получает 90%</div>
                          </div>
                        </label>
                        <label className={`flex-1 flex items-center gap-2 p-3 rounded border cursor-pointer transition-colors ${
                          marketplaceMode === 'owner_dispatcher' ? 'border-orange-500 bg-orange-50 text-orange-700' : 'border-gray-200 hover:bg-gray-50'
                        }`}>
                          <input type="radio" name="mpMode" value="owner_dispatcher"
                            checked={marketplaceMode === 'owner_dispatcher'}
                            onChange={() => setMarketplaceMode('owner_dispatcher')}
                            className="accent-orange-600" />
                          <div>
                            <div className="text-sm font-medium">📋 Я диспетчер</div>
                            <div className="text-xs text-gray-500">Получаю 10% диспетчерских</div>
                          </div>
                        </label>
                      </div>
                    </div>

                    {/* Срок оплаты */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Срок оплаты (дней) *</label>
                      <div className="flex items-center gap-3">
                        <input type="number" min={1} max={90}
                          value={paymentTermsDays}
                          onChange={(e) => {
                            const v = Number(e.target.value) || 7;
                            setPaymentTermsDays(v);
                            setShowExtendedPaymentWarning(v > 7);
                          }}
                          className="w-24 p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                        />
                        <span className="text-sm text-gray-500">Стандарт: 7 дней</span>
                      </div>
                      {paymentTermsDays > 7 && (
                        <div className="mt-2 p-3 bg-red-50 border border-red-200 rounded animate-pulse">
                          <div className="flex items-start gap-2">
                            <span className="text-red-600 text-lg">⚠️</span>
                            <div>
                              <p className="text-sm font-medium text-red-800">Увеличенный срок оплаты: {paymentTermsDays} дн.</p>
                              <p className="text-xs text-red-600 mt-1">
                                Исполнители увидят предупреждение об изменённых условиях оплаты.
                                Это может снизить количество откликов на заявку.
                              </p>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}

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
              <AddressAutocomplete
                value={objectAddress}
                onChange={setObjectAddress}
                placeholder="Например: Москва, Красная площадь"
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
                <label className="block text-sm font-medium text-gray-700 mb-1">Длительность (ч)</label>
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
                <label className="block text-sm font-medium text-gray-700 mb-1">Ставка (₽)</label>
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
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Ожидаемая сумма (₽)
                <span className="text-xs text-gray-500 ml-2">
                  {parseFloat(shiftDuration) > 0 && parseFloat(clientRate) > 0 && (
                    <span className="text-blue-600">✨ авторасчёт</span>
                  )}
                </span>
              </label>
              <input
                type="number"
                step="100"
                min="0"
                value={estimatedAmount}
                onChange={(e) => setEstimatedAmount(e.target.value)}
                className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none bg-gray-50"
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

            {/* === МОДАЛЬНОЕ ОКНО ДОБАВЛЕНИЯ ЗНАЧЕНИЯ === */}
            {customAttrModal && (
              <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[60] p-4">
                <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
                  <h3 className="text-lg font-bold text-gray-900 mb-4">
                    Новое значение: {customAttrModal.attrName}
                  </h3>
                  {customError && (
                    <div className="mb-3 p-2 bg-red-50 border border-red-200 text-red-700 text-sm rounded">
                      {customError}
                    </div>
                  )}
                  <div className="space-y-3">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Значение *</label>
                      <input
                        type="text"
                        value={customValue}
                        onChange={(e) => { setCustomValue(e.target.value); setCustomError(''); }}
                        className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                        placeholder={`Например: ${customAttrModal.attrName}`}
                        autoFocus
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Числовое значение <span className="text-gray-400">(опционально)</span>
                      </label>
                      <input
                        type="number"
                        step="any"
                        value={customNumericValue}
                        onChange={(e) => setCustomNumericValue(e.target.value)}
                        className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                        placeholder="36"
                      />
                    </div>
                  </div>
                  <div className="flex justify-end gap-3 mt-6">
                    <button
                      type="button"
                      onClick={() => setCustomAttrModal(null)}
                      className="px-4 py-2 border border-gray-300 text-gray-700 rounded hover:bg-gray-50"
                      disabled={addingCustom}
                    >Отмена</button>
                    <button
                      type="button"
                      onClick={async () => {
                        if (!customValue.trim()) {
                          setCustomError('Введите значение');
                          return;
                        }
                        // Check duplicates locally
                        const attr = subcategoryAttributes.find(a => a.id === customAttrModal.attrId);
                        if (attr?.options.some(o => o.value.toLowerCase() === customValue.trim().toLowerCase())) {
                          setCustomError(`Значение "${customValue.trim()}" уже существует`);
                          return;
                        }
                        setAddingCustom(true);
                        setCustomError('');
                        try {
                          const newOpt = await addCustomOption(customAttrModal.attrId, {
                            value: customValue.trim(),
                            numeric_value: customNumericValue ? parseFloat(customNumericValue) : null,
                          });
                          // Update attributes list
                          setSubcategoryAttributes(prev => prev.map(a =>
                            a.id === customAttrModal.attrId
                              ? { ...a, options: [...a.options, newOpt] }
                              : a
                          ));
                          // Auto-select new value
                          setAttributeValues(prev => ({ ...prev, [customAttrModal.slug]: newOpt.value }));
                          setCustomAttrModal(null);
                        } catch (err: any) {
                          const msg = err.response?.data?.detail || 'Ошибка при добавлении';
                          setCustomError(msg);
                        } finally {
                          setAddingCustom(false);
                        }
                      }}
                      className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                      disabled={addingCustom}
                    >{addingCustom ? 'Добавление...' : 'Добавить'}</button>
                  </div>
                </div>
              </div>
            )}

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
                disabled={saving || loadingClients}
              >
                {saving ? 'Сохранение...' : (request ? 'Сохранить' : 'Создать заявку')}
              </button>
              {request && (
                <button
                  type="button"
                  onClick={async () => {
                    setPublishing(true);
                    try {
                      const result = await requestsApi.publish(request.id);
                      alert(result.message);
                    } catch (err: any) {
                      alert(err.response?.data?.detail || 'Ошибка публикации');
                    } finally {
                      setPublishing(false);
                    }
                  }}
                  className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
                  disabled={publishing || saving}
                >
                  {publishing ? 'Публикация...' : '🌐 Опубликовать в маркетплейсе'}
                </button>
              )}
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default RequestFormModal;
