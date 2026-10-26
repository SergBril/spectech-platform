import React, { useState, useEffect, useMemo } from 'react';
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
import { useAuth } from '../contexts/AuthContext';

interface Contractor {
  id: number;
  name: string;
  type: string;
}

interface VehicleWithDriver {
  id: number;
  name: string;
  category_id: number | null;
  driver_id: number | null;
  driver_name: string;
  hourly_rate: number | null;
  shift_rate: number | null;
  attributes: Record<string, any>;
}

/**
 * Региональные пресеты для минимальных смен и ставок.
 * В будущем можно загружать из API /api/v1/regions/pricing
 */
const REGION_PRESETS: Record<string, {
  label: string;
  minShiftHours: number;       // Минимальная смена (работа + подача)
  workHours: number;           // Часы работы
  deliveryHours: number;       // Часы подачи
  defaultShiftRate: number;    // Ставка за смену по умолчанию
  defaultHourlyRate: number;   // Почасовая ставка по умолчанию
  deliveryCostPerKm: number;   // Стоимость доставки за км (для негабарита)
  description: string;
}> = {
  moscow: {
    label: '🏙️ Москва',
    minShiftHours: 8,
    workHours: 7,
    deliveryHours: 1,
    defaultShiftRate: 35000,
    defaultHourlyRate: 5000,
    deliveryCostPerKm: 100,
    description: 'Мин. смена 8ч (7ч работа + 1ч подача)',
  },
  moscow_oblast: {
    label: '🌄 Московская область',
    minShiftHours: 8,
    workHours: 7,
    deliveryHours: 1,
    defaultShiftRate: 35000,
    defaultHourlyRate: 5000,
    deliveryCostPerKm: 100,
    description: 'Мин. смена 8ч (7ч работа + 1ч подача) + км от МКАД',
  },
  volgograd: {
    label: '🏗️ Волгоградская область',
    minShiftHours: 4,
    workHours: 3,
    deliveryHours: 1,
    defaultShiftRate: 20000,
    defaultHourlyRate: 3500,
    deliveryCostPerKm: 80,
    description: 'Мин. смена 4ч (3ч работа + 1ч подача)',
  },
  hourly_no_min: {
    label: '⏱️ Почасовая (без мин. смены)',
    minShiftHours: 1,
    workHours: 1,
    deliveryHours: 0,
    defaultShiftRate: 0,
    defaultHourlyRate: 3000,
    deliveryCostPerKm: 0,
    description: 'Оплата строго по часам, без минимальной смены',
  },
};

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

// Для заказчика: без дубля daily/shift
const CLIENT_RATE_TYPES: { value: RateType; label: string }[] = [
  { value: 'shift', label: 'За смену' },
  { value: 'hourly', label: 'Почасовая' },
  { value: 'fixed', label: 'Фиксированная цена' },
];

// Для владельца/диспетчера: все варианты
const OWNER_RATE_TYPES: { value: RateType; label: string }[] = [
  { value: 'hourly', label: 'Почасовая' },
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

const isClientUser = (user: any): boolean => {
  const role = user?.role || user?.user_type || '';
  return role === 'client' || role === 'customer' || role === '';
};

const isTodayOrEarlier = (dateStr: string): boolean => {
  if (!dateStr) return false;
  const selected = new Date(dateStr);
  const today = new Date();
  return selected.toDateString() <= today.toDateString();
};

export const RequestFormModal: React.FC<Props> = ({
  request,
  onClose,
  onSave,
  vehicleId,
  vehicleName,
}) => {
  const { user } = useAuth();
  const isClient = useMemo(() => isClientUser(user), [user]);

  const [workType, setWorkType] = useState(request?.work_type || '');
  const [objectAddress, setObjectAddress] = useState(request?.object_address || '');
  const [requestType, setRequestType] = useState<RequestType>(request?.request_type || 'one_time');
  const [plannedStart, setPlannedStart] = useState(toLocalDatetime(request?.planned_start));
  const [plannedEnd, setPlannedEnd] = useState(toLocalDatetime(request?.planned_end));
  const [shiftDuration, setShiftDuration] = useState(request?.shift_duration_hours?.toString() || '8');
  const [clientRate, setClientRate] = useState(request?.client_rate?.toString() || '');
  const [rateType, setRateType] = useState<RateType>((request?.rate_type as RateType) || (isClient ? 'shift' : 'hourly'));
  const [estimatedAmount, setEstimatedAmount] = useState(request?.estimated_amount?.toString() || '');
  const [sourceChannel, setSourceChannel] = useState<SourceChannel>((request?.source_channel as SourceChannel) || 'web');
  const [priority, setPriority] = useState<Priority>((request?.priority as Priority) || 'normal');
  const [status, setStatus] = useState<RequestStatus>(request?.status || 'new');
  const [comment, setComment] = useState(request?.comment || '');
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [error, setError] = useState('');

  // Регион
  const [selectedRegion, setSelectedRegion] = useState<string>('moscow');

  // Клиент
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

  // Назначение
  const [assignmentMode, setAssignmentMode] = useState<'own' | 'marketplace'>(isClient ? 'marketplace' : 'own');
  const [marketplaceMode, setMarketplaceMode] = useState<'client' | 'owner_dispatcher'>(isClient ? 'client' : 'owner_dispatcher');
  const [paymentTermsDays, setPaymentTermsDays] = useState<number>(isClient ? 0 : 7);
  const [showExtendedPaymentWarning, setShowExtendedPaymentWarning] = useState(false);

  // Техника с водителями
  const [vehiclesWithDrivers, setVehiclesWithDrivers] = useState<VehicleWithDriver[]>([]);
  const [selectedVehicleId, setSelectedVehicleId] = useState<number | null>(request?.assigned_vehicle_id || null);
  const [loadingVehicles, setLoadingVehicles] = useState(false);

  // Доставка техники
  const [needsDelivery, setNeedsDelivery] = useState(false);
  const [deliveryCost, setDeliveryCost] = useState<string>('');

  // Custom attribute modal
  const [customAttrModal, setCustomAttrModal] = useState<{ attrId: number; attrName: string; slug: string } | null>(null);
  const [customValue, setCustomValue] = useState('');
  const [customNumericValue, setCustomNumericValue] = useState('');
  const [addingCustom, setAddingCustom] = useState(false);
  const [customError, setCustomError] = useState('');

  // Текущий пресет региона
  const regionPreset = REGION_PRESETS[selectedRegion] || REGION_PRESETS['moscow'];

  // Инициализация режима для клиента
  useEffect(() => {
    if (isClient) {
      setAssignmentMode('marketplace');
      setMarketplaceMode('client');
      setPaymentTermsDays(0);
      setShowExtendedPaymentWarning(false);
      setSourceChannel('web');
    } else {
      const role = user?.role || user?.user_type || '';
      if (role === 'owner' || role === 'dispatcher' || role === 'owner_dispatcher') {
        setMarketplaceMode('owner_dispatcher');
        setPaymentTermsDays(7);
      } else {
        setMarketplaceMode('client');
        setPaymentTermsDays(0);
      }
    }
  }, [user, isClient]);

  // Загрузка данных
  useEffect(() => {
    const loadData = async () => {
      // Клиенты (только для не-заказчиков)
      if (!isClient) {
        try {
          const res = await apiClient.get('/contractors', { params: { type: 'client', limit: 500 } });
          const list = Array.isArray(res.data) ? res.data : [];
          setClients(list);
          if (!request && !selectedClientId && list.length > 0) setSelectedClientId(list[0].id);
        } catch (e) { console.warn('Failed to load clients:', e); }
        setLoadingClients(false);
      } else {
        setLoadingClients(false);
      }

      // Каталог
      try {
        const tree = await getCatalogTree();
        setCatalogTree(tree);
      } catch (e) { console.warn('Failed to load catalog:', e); }

      // Техника с водителями (только для не-заказчиков)
      if (!isClient) {
        try {
          setLoadingVehicles(true);
          const res = await apiClient.get('/vehicles', { params: { limit: 500, include_driver: true } });
          const raw = res.data;
          const list = Array.isArray(raw) ? raw : (raw?.items || raw?.data || []);
          setVehiclesWithDrivers(list.map((v: any) => ({
            id: v.id,
            name: v.name || v.license_plate || `#${v.id}`,
            category_id: v.category_id ?? null,
            driver_id: v.driver_id ?? v.operator_id ?? null,
            driver_name: v.driver_name || v.operator_name || '',
            hourly_rate: v.hourly_rate ?? null,
            shift_rate: v.shift_rate ?? null,
            attributes: v.attributes || {},
          })));
        } catch (e) { console.warn('Failed to load vehicles:', e); }
        setLoadingVehicles(false);
      }
    };
    loadData();
  }, [isClient]);

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
        .then(attrs => setSubcategoryAttributes(attrs))
        .catch(() => setSubcategoryAttributes([]))
        .finally(() => setLoadingAttributes(false));
    } else {
      setSubcategoryAttributes([]);
    }
  }, [selectedSubcategoryId]);

  // 🆕 УМНЫЙ АВТО-РАСЧЁТ суммы + предупреждения о мин. смене
  useEffect(() => {
    const hours = parseFloat(shiftDuration) || 0;
    const rate = parseFloat(clientRate) || 0;
    const minHours = regionPreset.minShiftHours;

    let total = 0;
    let warning: string | null = null;

    if (rate > 0) {
      switch (rateType) {
        case 'hourly':
          total = hours * rate;
          // Предупреждение о минимальной смене для почасовой (кроме пресета "без минимума")
          if (selectedRegion !== 'hourly_no_min' && hours > 0 && hours < minHours) {
            warning = `⚠️ Минимальная смена в регионе «${regionPreset.label}»: ${minHours}ч (${regionPreset.workHours}ч работа + ${regionPreset.deliveryHours}ч подача). Текущая длительность: ${hours}ч.`;
          }
          break;
        case 'shift':
          // Для «За смену» сумма = ставка (не зависит от часов)
          total = rate;
          break;
        case 'daily':
          total = rate;
          break;
        case 'fixed':
          total = rate;
          break;
      }
    }

    // Добавляем доставку
    if (needsDelivery && deliveryCost) {
      total += parseFloat(deliveryCost) || 0;
    }

    if (total > 0) {
      setEstimatedAmount(total.toString());
    }

    // Устанавливаем предупреждение через отдельный state ниже
    // (используем ref или просто рендерим inline)
  }, [shiftDuration, clientRate, rateType, selectedRegion, regionPreset, needsDelivery, deliveryCost]);

  // Автозаполнение ставки из выбранной техники
  useEffect(() => {
    if (selectedVehicleId && !request && !clientRate) {
      const v = vehiclesWithDrivers.find(v => v.id === selectedVehicleId);
      if (v) {
        if (v.hourly_rate) { setClientRate(v.hourly_rate.toString()); setRateType('hourly'); }
        else if (v.shift_rate) { setClientRate(v.shift_rate.toString()); setRateType('shift'); }
      }
    }
  }, [selectedVehicleId, vehiclesWithDrivers, request, clientRate]);

  // Фильтрация техники по категории/подкатегории и атрибутам
  const filteredVehicles = useMemo(() => {
    return vehiclesWithDrivers.filter(v => {
      if (selectedSubcategoryId && v.category_id !== selectedSubcategoryId) return false;
      if (!selectedSubcategoryId && selectedCategoryId && v.category_id !== selectedCategoryId) return false;
      for (const [slug, val] of Object.entries(attributeValues)) {
        if (val && v.attributes?.[slug] !== val) return false;
      }
      return true;
    });
  }, [vehiclesWithDrivers, selectedCategoryId, selectedSubcategoryId, attributeValues]);

  // Предупреждение о мин. смене (вычисляем отдельно для рендера)
  const minShiftWarning = useMemo(() => {
    const hours = parseFloat(shiftDuration) || 0;
    const minHours = regionPreset.minShiftHours;
    if (rateType === 'hourly' && selectedRegion !== 'hourly_no_min' && hours > 0 && hours < minHours) {
      return `⚠️ Минимальная смена в регионе «${regionPreset.label}»: ${minHours}ч (${regionPreset.workHours}ч работа + ${regionPreset.deliveryHours}ч подача). Текущая длительность: ${hours}ч.`;
    }
    return null;
  }, [shiftDuration, rateType, selectedRegion, regionPreset]);

  // Предупреждение о срочной заявке
  const isUrgentRequest = isTodayOrEarlier(plannedStart);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!workType.trim()) { setError('Введите тип работы'); return; }
    if (!objectAddress.trim()) { setError('Введите адрес объекта'); return; }
    if (!plannedStart || !plannedEnd) { setError('Укажите даты начала и окончания'); return; }

    // Для не-заказчиков: клиент обязателен
    if (!isClient && !selectedClientId) { setError('Выберите клиента'); return; }

    // Marketplace validation
    if (assignmentMode === 'marketplace') {
      const start = new Date(plannedStart);
      const end = new Date(plannedEnd);
      if (end <= start) { setError('Дата окончания должна быть позже даты начала'); return; }
      if (!clientRate || Number(clientRate) <= 0) { setError('Укажите бюджет / стоимость смены'); return; }
    }

    // Own vehicle validation
    if (!isClient && assignmentMode === 'own' && !selectedVehicleId) {
      setError('Выберите технику с водителем');
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
        priority: priority,
        comment: comment.trim() || undefined,
        vehicle_category_id: selectedSubcategoryId || undefined,
        region: selectedRegion,
      };

      // Для заказчика: source_channel=web, marketplace_mode=client, payment_terms=0
      if (isClient) {
        payload.source_channel = 'web';
        payload.marketplace_mode = 'client';
        payload.payment_terms_days = 0;
      } else {
        payload.source_channel = assignmentMode === 'marketplace' ? 'marketplace' : sourceChannel;
        payload.marketplace_mode = assignmentMode === 'marketplace' ? marketplaceMode : undefined;
        payload.payment_terms_days = assignmentMode === 'marketplace' ? paymentTermsDays : undefined;
        payload.client_id = selectedClientId;
      }

      if (shiftDuration) payload.shift_duration_hours = parseFloat(shiftDuration);
      if (clientRate) payload.client_rate = parseFloat(clientRate);
      if (estimatedAmount) payload.estimated_amount = parseFloat(estimatedAmount);

      // Назначение техники и водителя
      if (!isClient && assignmentMode === 'own' && selectedVehicleId) {
        payload.assigned_vehicle_id = selectedVehicleId;
        const selectedV = vehiclesWithDrivers.find(v => v.id === selectedVehicleId);
        if (selectedV?.driver_id) {
          payload.driver_id = selectedV.driver_id;
          payload.assigned_operator_id = selectedV.driver_id;
        }
      }

      // Доставка техники
      if (needsDelivery && deliveryCost) {
        payload.delivery_cost = parseFloat(deliveryCost);
        payload.needs_delivery = true;
      }

      if (request) payload.status = status;

      await onSave(payload);
    } catch (err: any) {
      setSaving(false);
      const msg = err.response?.data?.detail || err.response?.data?.message || 'Ошибка при сохранении';
      setError(msg);
    }
  };

  // Текст для отображения режима маркетплейса
  const marketplaceModeLabel = marketplaceMode === 'owner_dispatcher'
    ? { icon: '📋', title: 'Диспетчер / Владелец техники', desc: 'Вы получаете 10% комиссии. Стандартный срок оплаты: 7 дней.' }
    : { icon: '🏪', title: 'Заказчик', desc: 'Предоплата 100%. Счёт выставляется вашей компании.' };

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

          {/* Предупреждение о срочной заявке для заказчика */}
          {isClient && isUrgentRequest && (
            <div className="mb-4 p-4 bg-yellow-50 border border-yellow-300 rounded-lg animate-pulse">
              <div className="flex items-start gap-2">
                <span className="text-yellow-600 text-xl">⏰</span>
                <div>
                  <p className="text-sm font-semibold text-yellow-800">Заявка на сегодня / срочная</p>
                  <p className="text-xs text-yellow-700 mt-1">
                    Оплата может не успеть пройти до начала работ. Возможно потребуется оставить залог
                    до поступления оплаты на расчётный счёт исполнителя.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Выбранная техника (если передана извне) */}
          {vehicleId && vehicleName && (
            <div className="mb-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <p className="text-xs text-blue-600 uppercase font-semibold mb-1">Выбранная техника</p>
              <p className="text-lg font-bold text-gray-900">🚜 {vehicleName}</p>
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">{error}</div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Тип заявки + Приоритет */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Тип заявки *</label>
                <select value={requestType} onChange={(e) => setRequestType(e.target.value as RequestType)}
                  className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none">
                  {REQUEST_TYPES.map(t => (<option key={t.value} value={t.value}>{t.label}</option>))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Приоритет *</label>
                <select value={priority} onChange={(e) => setPriority(e.target.value as Priority)}
                  className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none">
                  {PRIORITIES.map(p => (<option key={p.value} value={p.value}>{p.label}</option>))}
                </select>
              </div>
            </div>

            {/* Клиент — ТОЛЬКО для не-заказчиков */}
            {!isClient && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Клиент *</label>
                <select value={selectedClientId ?? ''} onChange={(e) => setSelectedClientId(Number(e.target.value) || null)}
                  className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none" disabled={loadingClients}>
                  <option value="">Выберите клиента</option>
                  {clients.map(cl => (<option key={cl.id} value={cl.id}>{cl.name}</option>))}
                </select>
              </div>
            )}

            {/* === ВЫБОР РЕГИОНА === */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">🗺️ Регион работ</label>
              <select
                value={selectedRegion}
                onChange={(e) => {
                  setSelectedRegion(e.target.value);
                  // Автозаполнение ставки при смене региона (только для новых заявок)
                  if (!request && !clientRate) {
                    const preset = REGION_PRESETS[e.target.value];
                    if (preset) {
                      if (rateType === 'shift') {
                        setClientRate(preset.defaultShiftRate.toString());
                      } else if (rateType === 'hourly') {
                        setClientRate(preset.defaultHourlyRate.toString());
                      }
                      // Автозаполнение длительности мин. сменой
                      if (rateType === 'shift') {
                        setShiftDuration(preset.minShiftHours.toString());
                      }
                    }
                  }
                }}
                className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
              >
                {Object.entries(REGION_PRESETS).map(([key, preset]) => (
                  <option key={key} value={key}>{preset.label}</option>
                ))}
              </select>
              <p className="text-xs text-gray-500 mt-1">{regionPreset.description}</p>
            </div>

            {/* Категория и подкатегория */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Категория техники</label>
                <select value={selectedCategoryId ?? ''} onChange={(e) => {
                  setSelectedCategoryId(Number(e.target.value) || null);
                  setSelectedSubcategoryId(null);
                  setAttributeValues({});
                }} className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none">
                  <option value="">Выберите категорию</option>
                  {catalogTree.map(cat => (<option key={cat.id} value={cat.id}>{cat.name}</option>))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Подкатегория</label>
                <select value={selectedSubcategoryId ?? ''} onChange={(e) => {
                  setSelectedSubcategoryId(Number(e.target.value) || null);
                  setAttributeValues({});
                }} className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none" disabled={!selectedCategoryId}>
                  <option value="">Выберите подкатегорию</option>
                  {(catalogTree.find(c => c.id === selectedCategoryId)?.subcategories || []).map(sub => (
                    <option key={sub.id} value={sub.id}>{sub.name}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Атрибуты подкатегории */}
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
                          <select value={attributeValues[attr.slug] || ''}
                            onChange={(e) => setAttributeValues(prev => ({ ...prev, [attr.slug]: e.target.value }))}
                            className="flex-1 p-1.5 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none">
                            <option value="">Выберите</option>
                            {attr.options.map(opt => (<option key={opt.id} value={opt.value}>{opt.value}</option>))}
                          </select>
                          {attr.allow_custom_values && (
                            <button type="button" onClick={() => {
                              setCustomAttrModal({ attrId: attr.id, attrName: attr.name, slug: attr.slug });
                              setCustomValue(''); setCustomNumericValue(''); setCustomError('');
                            }} className="px-2 py-1 bg-blue-100 text-blue-700 rounded hover:bg-blue-200 text-sm font-bold transition-colors" title="Добавить новое значение">+</button>
                          )}
                        </div>
                      ) : (
                        <input type={attr.data_type === 'number' ? 'number' : 'text'}
                          value={attributeValues[attr.slug] || ''}
                          onChange={(e) => setAttributeValues(prev => ({ ...prev, [attr.slug]: e.target.value }))}
                          className="w-full p-1.5 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                          placeholder={attr.data_type === 'number' ? '0' : ''} />
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* === НАЗНАЧЕНИЕ === */}
            <div className="p-4 border border-gray-200 rounded-lg">
              {isClient ? (
                /* === РЕЖИМ ЗАКАЗЧИКА === */
                <div className="space-y-3">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-lg">🏪</span>
                    <label className="block text-sm font-semibold text-gray-700">
                      Заявка для платформы СпецТехника Про
                    </label>
                  </div>
                  <p className="text-xs text-gray-500">
                    Ваша заявка будет обработана менеджерами платформы.
                    После подтверждения вам будет выставлен счёт.
                    Техника и водитель будут назначены после поступления оплаты.
                  </p>
                  <div className="p-3 bg-purple-50 border border-purple-200 rounded">
                    <div className="flex items-center gap-2">
                      <span className="text-purple-600">💳</span>
                      <span className="text-sm font-medium text-purple-800">
                        Предоплата 100% • Счёт формируется автоматически
                      </span>
                    </div>
                  </div>
                </div>
              ) : (
                /* === РЕЖИМ ВЛАДЕЛЬЦА / ДИСПЕТЧЕРА === */
                <>
                  <label className="block text-sm font-semibold text-gray-700 mb-3">Назначение заявки</label>
                  <div className="flex gap-4 mb-3">
                    <label className={`flex items-center gap-2 cursor-pointer px-4 py-2 rounded-lg border transition-all ${
                      assignmentMode === 'own' ? 'border-blue-500 bg-blue-50 text-blue-700' : 'border-gray-200 hover:bg-gray-50'
                    }`}>
                      <input type="radio" name="assignmentMode" value="own"
                        checked={assignmentMode === 'own'} onChange={() => setAssignmentMode('own')}
                        className="accent-blue-600" />
                      <span className="text-sm font-medium">🚜 Своя техника + водитель</span>
                    </label>
                    <label className={`flex items-center gap-2 cursor-pointer px-4 py-2 rounded-lg border transition-all ${
                      assignmentMode === 'marketplace' ? 'border-green-500 bg-green-50 text-green-700' : 'border-gray-200 hover:bg-gray-50'
                    }`}>
                      <input type="radio" name="assignmentMode" value="marketplace"
                        checked={assignmentMode === 'marketplace'} onChange={() => setAssignmentMode('marketplace')}
                        className="accent-green-600" />
                      <span className="text-sm font-medium">🌐 Маркетплейс</span>
                    </label>
                  </div>

                  {assignmentMode === 'own' && (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Выберите технику с водителем *
                        {filteredVehicles.length < vehiclesWithDrivers.length && (
                          <span className="text-xs text-gray-400 ml-2">
                            (отфильтровано: {filteredVehicles.length} из {vehiclesWithDrivers.length})
                          </span>
                        )}
                      </label>
                      <select
                        value={selectedVehicleId ?? ''}
                        onChange={(e) => setSelectedVehicleId(Number(e.target.value) || null)}
                        className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                        disabled={loadingVehicles}
                      >
                        <option value="">
                          {loadingVehicles ? 'Загрузка...' : filteredVehicles.length === 0 ? 'Нет подходящей техники' : 'Выберите технику с водителем'}
                        </option>
                        {filteredVehicles.map(v => (
                          <option key={v.id} value={v.id}>
                            🚜 {v.name} {v.driver_name ? `— 👷 ${v.driver_name}` : '— ⚠️ Без водителя'}
                          </option>
                        ))}
                      </select>
                      {selectedVehicleId && (() => {
                        const sv = vehiclesWithDrivers.find(v => v.id === selectedVehicleId);
                        if (!sv) return null;
                        return (
                          <div className="mt-2 p-3 bg-blue-50 rounded border border-blue-200 text-sm">
                            <div className="flex justify-between">
                              <span className="font-medium text-gray-900">🚜 {sv.name}</span>
                              <span className="text-gray-600">
                                {sv.hourly_rate ? `${sv.hourly_rate} ₽/час` : sv.shift_rate ? `${sv.shift_rate} ₽/смена` : 'Ставка не указана'}
                              </span>
                            </div>
                            {sv.driver_name ? (
                              <div className="text-green-700 mt-1">👷 Водитель: {sv.driver_name}</div>
                            ) : (
                              <div className="text-orange-600 mt-1">⚠️ Водитель не назначен</div>
                            )}
                          </div>
                        );
                      })()}
                    </div>
                  )}

                  {assignmentMode === 'marketplace' && (
                    <div className="space-y-3 bg-green-50 p-4 rounded border border-green-200">
                      <p className="text-sm text-green-700 font-medium">📢 Заявка будет опубликована в маркетплейсе</p>

                      {/* Автоматически определённый режим (read-only) */}
                      <div className={`p-3 rounded border ${
                        marketplaceMode === 'owner_dispatcher' ? 'bg-orange-50 border-orange-200' : 'bg-purple-50 border-purple-200'
                      }`}>
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-lg">{marketplaceModeLabel.icon}</span>
                          <span className={`text-sm font-semibold ${
                            marketplaceMode === 'owner_dispatcher' ? 'text-orange-800' : 'text-purple-800'
                          }`}>Режим: {marketplaceModeLabel.title}</span>
                        </div>
                        <p className={`text-xs ${
                          marketplaceMode === 'owner_dispatcher' ? 'text-orange-600' : 'text-purple-600'
                        }`}>{marketplaceModeLabel.desc}</p>
                      </div>

                      {/* Срок оплаты */}
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Срок оплаты (дней) *</label>
                        <div className="flex items-center gap-3">
                          <input type="number" min={0} max={90}
                            value={paymentTermsDays}
                            onChange={(e) => {
                              const v = Math.max(0, Math.min(90, Number(e.target.value) || 0));
                              setPaymentTermsDays(v);
                              setShowExtendedPaymentWarning(v > 7);
                            }}
                            disabled={marketplaceMode === 'client'}
                            className={`w-24 p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none ${
                              marketplaceMode === 'client' ? 'bg-gray-100 cursor-not-allowed' : ''
                            }`}
                          />
                          <span className="text-sm text-gray-500">
                            {marketplaceMode === 'client' ? 'Предоплата 100%' : 'Стандарт: 7 дней'}
                          </span>
                        </div>
                        {showExtendedPaymentWarning && marketplaceMode === 'owner_dispatcher' && (
                          <div className="mt-2 p-3 bg-red-50 border border-red-200 rounded animate-pulse">
                            <div className="flex items-start gap-2">
                              <span className="text-red-600 text-lg">⚠️</span>
                              <div>
                                <p className="text-sm font-medium text-red-800">Увеличенный срок оплаты: {paymentTermsDays} дн.</p>
                                <p className="text-xs text-red-600 mt-1">
                                  Исполнители увидят предупреждение. Это может снизить количество откликов.
                                </p>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Тип работы */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Тип работы *</label>
              <input type="text" value={workType} onChange={(e) => setWorkType(e.target.value)}
                className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                placeholder="Например: Земляные работы" required />
            </div>

            {/* Адрес */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Адрес объекта *</label>
              <AddressAutocomplete value={objectAddress} onChange={setObjectAddress}
                placeholder="Например: Москва, Красная площадь" />
            </div>

            {/* Даты */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Плановое начало *</label>
                <input type="datetime-local" value={plannedStart} onChange={(e) => setPlannedStart(e.target.value)}
                  className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none" required />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Плановое окончание *</label>
                <input type="datetime-local" value={plannedEnd} onChange={(e) => setPlannedEnd(e.target.value)}
                  className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none" required />
              </div>
            </div>

            {/* Длительность, ставка, тип ставки */}
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Длительность (ч)
                  {rateType === 'shift' && (
                    <span className="text-xs text-gray-400 ml-1">(информационно)</span>
                  )}
                </label>
                <input type="number" step="0.5" min="0" value={shiftDuration} onChange={(e) => setShiftDuration(e.target.value)}
                  className={`w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none ${
                    rateType === 'shift' ? 'bg-gray-50' : ''
                  }`} placeholder={regionPreset.minShiftHours.toString()} />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {rateType === 'shift' ? 'Стоимость смены (₽)' : isClient ? 'Бюджет / Ставка (₽)' : 'Ставка (₽)'}
                </label>
                <input type="number" step="100" min="0" value={clientRate} onChange={(e) => setClientRate(e.target.value)}
                  className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                  placeholder={rateType === 'shift' ? regionPreset.defaultShiftRate.toString() : regionPreset.defaultHourlyRate.toString()} />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Тип ставки</label>
                <select value={rateType} onChange={(e) => {
                  const newType = e.target.value as RateType;
                  setRateType(newType);
                  // При переключении на «За смену» ставим мин. смену региона
                  if (newType === 'shift' && !request) {
                    setShiftDuration(regionPreset.minShiftHours.toString());
                    if (!clientRate) setClientRate(regionPreset.defaultShiftRate.toString());
                  }
                  // При переключении на почасовую
                  if (newType === 'hourly' && !request && !clientRate) {
                    setClientRate(regionPreset.defaultHourlyRate.toString());
                  }
                }}
                  className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none">
                  {(isClient ? CLIENT_RATE_TYPES : OWNER_RATE_TYPES).map(r => (
                    <option key={r.value} value={r.value}>{r.label}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* ⚠️ Предупреждение о минимальной смене */}
            {minShiftWarning && (
              <div className="p-3 bg-yellow-50 border border-yellow-300 rounded-lg">
                <p className="text-sm text-yellow-800">{minShiftWarning}</p>
              </div>
            )}

            {/* 🚛 Доставка техники (для экскаваторов, бульдозеров и т.д.) */}
            <div className="p-4 border border-gray-200 rounded-lg">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={needsDelivery}
                  onChange={(e) => setNeedsDelivery(e.target.checked)}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span className="text-sm font-medium text-gray-700">
                  🚛 Требуется доставка техники до объекта
                </span>
              </label>
              <p className="text-xs text-gray-500 mt-1 ml-6">
                Для техники, которая не может передвигаться по городу (экскаваторы, бульдозеры, катки и т.д.)
              </p>
              {needsDelivery && (
                <div className="mt-3 ml-6">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Стоимость доставки (туда и обратно, ₽)
                  </label>
                  <input
                    type="number"
                    step="500"
                    min="0"
                    value={deliveryCost}
                    onChange={(e) => setDeliveryCost(e.target.value)}
                    className="w-full max-w-xs p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                    placeholder={`~${regionPreset.deliveryCostPerKm} ₽/км × расстояние`}
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Ориентировочная ставка: {regionPreset.deliveryCostPerKm} ₽/км. Включает доставку от базы до объекта и обратно.
                  </p>
                </div>
              )}
            </div>

            {/* Ожидаемая сумма */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Итого к оплате (₽)
                <span className="text-xs text-gray-500 ml-2">
                  {parseFloat(shiftDuration) > 0 && parseFloat(clientRate) > 0 && (
                    <span className="text-blue-600">✨ авторасчёт</span>
                  )}
                  {needsDelivery && parseFloat(deliveryCost) > 0 && (
                    <span className="text-orange-600 ml-1">+ доставка</span>
                  )}
                </span>
              </label>
              <input type="number" step="100" min="0" value={estimatedAmount} onChange={(e) => setEstimatedAmount(e.target.value)}
                className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none bg-gray-50" placeholder="40000" />
            </div>

            {/* Источник + Статус — Источник скрыт для заказчика */}
            <div className="grid grid-cols-2 gap-4">
              {!isClient && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Источник заявки</label>
                  <select value={sourceChannel} onChange={(e) => setSourceChannel(e.target.value as SourceChannel)}
                    className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none">
                    {SOURCE_CHANNELS.map(s => (<option key={s.value} value={s.value}>{s.label}</option>))}
                  </select>
                </div>
              )}
              {request && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Статус</label>
                  <select value={status} onChange={(e) => setStatus(e.target.value as RequestStatus)}
                    className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none">
                    {STATUSES.map(s => (<option key={s.value} value={s.value}>{s.label}</option>))}
                  </select>
                </div>
              )}
            </div>

            {/* Комментарий */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Комментарий</label>
              <textarea value={comment} onChange={(e) => setComment(e.target.value)} rows={2}
                className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                placeholder="Дополнительная информация" />
            </div>

            {/* Модальное окно добавления значения атрибута */}
            {customAttrModal && (
              <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[60] p-4">
                <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
                  <h3 className="text-lg font-bold text-gray-900 mb-4">Новое значение: {customAttrModal.attrName}</h3>
                  {customError && (<div className="mb-3 p-2 bg-red-50 border border-red-200 text-red-700 text-sm rounded">{customError}</div>)}
                  <div className="space-y-3">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Значение *</label>
                      <input type="text" value={customValue} onChange={(e) => { setCustomValue(e.target.value); setCustomError(''); }}
                        className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                        placeholder={`Например: ${customAttrModal.attrName}`} autoFocus />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Числовое значение <span className="text-gray-400">(опционально)</span></label>
                      <input type="number" step="any" value={customNumericValue} onChange={(e) => setCustomNumericValue(e.target.value)}
                        className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none" placeholder="36" />
                    </div>
                  </div>
                  <div className="flex justify-end gap-3 mt-6">
                    <button type="button" onClick={() => setCustomAttrModal(null)}
                      className="px-4 py-2 border border-gray-300 text-gray-700 rounded hover:bg-gray-50" disabled={addingCustom}>Отмена</button>
                    <button type="button" onClick={async () => {
                      if (!customValue.trim()) { setCustomError('Введите значение'); return; }
                      const attr = subcategoryAttributes.find(a => a.id === customAttrModal.attrId);
                      if (attr?.options.some(o => o.value.toLowerCase() === customValue.trim().toLowerCase())) {
                        setCustomError(`Значение "${customValue.trim()}" уже существует`); return;
                      }
                      setAddingCustom(true); setCustomError('');
                      try {
                        const newOpt = await addCustomOption(customAttrModal.attrId, {
                          value: customValue.trim(),
                          numeric_value: customNumericValue ? parseFloat(customNumericValue) : null,
                        });
                        setSubcategoryAttributes(prev => prev.map(a =>
                          a.id === customAttrModal.attrId ? { ...a, options: [...a.options, newOpt] } : a
                        ));
                        setAttributeValues(prev => ({ ...prev, [customAttrModal.slug]: newOpt.value }));
                        setCustomAttrModal(null);
                      } catch (err: any) {
                        setCustomError(err.response?.data?.detail || 'Ошибка при добавлении');
                      } finally { setAddingCustom(false); }
                    }} className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                      disabled={addingCustom}>{addingCustom ? 'Добавление...' : 'Добавить'}</button>
                  </div>
                </div>
              </div>
            )}

            {/* Кнопки */}
            <div className="flex justify-end space-x-3 pt-4 border-t">
              <button type="button" onClick={onClose}
                className="px-4 py-2 border border-gray-300 text-gray-700 rounded hover:bg-gray-50" disabled={saving}>Отмена</button>
              <button type="submit"
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                disabled={saving || loadingClients || loadingVehicles}>
                {saving ? 'Сохранение...' : (request ? 'Сохранить' : 'Создать заявку')}
              </button>
              {request && (
                <button type="button" onClick={async () => {
                  setPublishing(true);
                  try {
                    const result = await requestsApi.publish(request.id);
                    alert(result.message);
                  } catch (err: any) {
                    alert(err.response?.data?.detail || 'Ошибка публикации');
                  } finally { setPublishing(false); }
                }} className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
                  disabled={publishing || saving}>
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