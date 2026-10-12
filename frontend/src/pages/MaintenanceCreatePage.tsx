import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Layout from '../components/Layout'; // Layout уже здесь
import {
  createMaintenanceOrder,
  MaintenanceOrderType,
  MaintenancePriority,
  MaintenancePart,
  MaintenanceWork,
} from '../api/maintenance';
import toast from 'react-hot-toast';

interface VehicleOption {
  id: number;
  name: string;
  engine_hours?: number;
  next_maintenance_hours?: number;
  status: string;
}

const ORDER_TYPES: { value: MaintenanceOrderType; label: string; icon: string }[] = [
  { value: 'scheduled', label: 'Плановое ТО', icon: '🔧' },
  { value: 'repair', label: 'Ремонт', icon: '🛠️' },
  { value: 'diagnostic', label: 'Диагностика', icon: '🔍' },
  { value: 'inspection', label: 'Осмотр', icon: '👁️' },
];

const PRIORITIES: { value: MaintenancePriority; label: string; icon: string; color: string }[] = [
  { value: 'low', label: 'Низкий', icon: '🟢', color: 'border-gray-300' },
  { value: 'medium', label: 'Средний', icon: '🟡', color: 'border-blue-500' },
  { value: 'high', label: 'Высокий', icon: '🟠', color: 'border-orange-500' },
  { value: 'critical', label: 'Критичный', icon: '🔴', color: 'border-red-500' },
];

export const MaintenanceCreatePage: React.FC = () => {
  const navigate = useNavigate();
  const [vehicles, setVehicles] = useState<VehicleOption[]>([]);
  const [loadingVehicles, setLoadingVehicles] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  // Основная форма
  const [vehicleId, setVehicleId] = useState<number | ''>('');
  const [orderType, setOrderType] = useState<MaintenanceOrderType>('repair');
  const [priority, setPriority] = useState<MaintenancePriority>('medium');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [symptoms, setSymptoms] = useState('');
  const [plannedHours, setPlannedHours] = useState<string>('');
  const [notes, setNotes] = useState('');

  // Запчасти (dynamic form)
  const [parts, setParts] = useState<MaintenancePart[]>([]);

  // Работы (dynamic form)
  const [works, setWorks] = useState<MaintenanceWork[]>([]);

  useEffect(() => {
    loadVehicles();
  }, []);

  const loadVehicles = async () => {
    setLoadingVehicles(true);
    try {
      // Прямой запрос к API (т.к. нужен именно список своей компании)
      const token = localStorage.getItem('access_token');
      const companyId = localStorage.getItem('spectech_current_company_id');

      const response = await fetch('http://localhost:8000/api/v1/vehicles?limit=100', {
        headers: {
          Authorization: `Bearer ${token}`,
          'X-Company-Id': companyId || '',
        },
      });

      if (response.ok) {
        const data = await response.json();
        setVehicles(data.items || data);
      } else {
        toast.error('Не удалось загрузить список техники');
      }
    } catch (error) {
      console.error('Error loading vehicles:', error);
      toast.error('Ошибка загрузки техники');
    } finally {
      setLoadingVehicles(false);
    }
  };

  // === Работа с запчастями ===
  const addPart = () => {
    setParts([
      ...parts,
      {
        name: '',
        part_number: '',
        quantity: 1,
        unit_price: 0,
        supplier: '',
        notes: '',
      },
    ]);
  };

  const updatePart = (index: number, field: keyof MaintenancePart, value: any) => {
    const newParts = [...parts];
    (newParts[index] as any)[field] = value;

    // Автоматический пересчёт total_price
    if (field === 'quantity' || field === 'unit_price') {
      const qty = parseFloat(String(newParts[index].quantity)) || 0;
      const price = parseFloat(String(newParts[index].unit_price)) || 0;
      newParts[index].total_price = qty * price;
    }

    setParts(newParts);
  };

  const removePart = (index: number) => {
    setParts(parts.filter((_, i) => i !== index));
  };

  // === Работа с работами ===
  const addWork = () => {
    setWorks([
      ...works,
      {
        work_type: '',
        description: '',
        labor_hours: 1,
        hourly_rate: 0,
      },
    ]);
  };

  const updateWork = (index: number, field: keyof MaintenanceWork, value: any) => {
    const newWorks = [...works];
    (newWorks[index] as any)[field] = value;

    // Автоматический пересчёт total_cost
    if (field === 'labor_hours' || field === 'hourly_rate') {
      const hours = parseFloat(String(newWorks[index].labor_hours)) || 0;
      const rate = parseFloat(String(newWorks[index].hourly_rate)) || 0;
      newWorks[index].total_cost = hours * rate;
    }

    setWorks(newWorks);
  };

  const removeWork = (index: number) => {
    setWorks(works.filter((_, i) => i !== index));
  };

  // === Расчёт итоговой стоимости ===
  const partsTotal = parts.reduce((sum, p) => sum + (p.total_price || 0), 0);
  const worksTotal = works.reduce((sum, w) => sum + (w.total_cost || 0), 0);
  const grandTotal = partsTotal + worksTotal;

  const formatCurrency = (amount: number) =>
    new Intl.NumberFormat('ru-RU', {
      style: 'currency',
      currency: 'RUB',
      minimumFractionDigits: 0,
    }).format(amount);

  // === Отправка формы ===
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!vehicleId) {
      toast.error('Выберите технику');
      return;
    }
    if (!title.trim()) {
      toast.error('Введите название');
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        vehicle_id: Number(vehicleId),
        order_type: orderType,
        priority: priority,
        title: title.trim(),
        description: description.trim() || undefined,
        symptoms: symptoms.trim() || undefined,
        planned_hours: plannedHours ? parseFloat(plannedHours) : undefined,
        notes: notes.trim() || undefined,
        parts: parts
          .filter((p) => p.name.trim())
          .map((p) => ({
            name: p.name.trim(),
            part_number: p.part_number?.trim() || undefined,
            quantity: Number(p.quantity),
            unit_price: Number(p.unit_price),
            supplier: p.supplier?.trim() || undefined,
            notes: p.notes?.trim() || undefined,
          })),
        works: works
          .filter((w) => w.work_type.trim())
          .map((w) => ({
            work_type: w.work_type.trim(),
            description: w.description?.trim() || undefined,
            labor_hours: Number(w.labor_hours),
            hourly_rate: Number(w.hourly_rate),
          })),
      };

      const created = await createMaintenanceOrder(payload);
      toast.success(`Наряд-заказ ${created.order_number} создан!`);
      navigate(`/maintenance/${created.id}`);
    } catch (error: any) {
      console.error('Error creating order:', error);
      toast.error(error?.response?.data?.detail || 'Ошибка создания наряд-заказа');
    } finally {
      setSubmitting(false);
    }
  };

  // ИСПРАВЛЕНО: Убран Navbar, всё содержимое обернуто в Layout
  return (
    <Layout>
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-6">
          <button
            onClick={() => navigate('/maintenance')}
            className="text-blue-600 hover:text-blue-700 text-sm mb-2"
          >
            ← Назад к списку
          </button>
          <h1 className="text-3xl font-bold text-gray-900">➕ Создать наряд-заказ</h1>
          <p className="text-gray-600 mt-1">
            Заполните информацию о работах, запчастях и трудозатратах
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Основная информация */}
          <div className="bg-white rounded-lg shadow-sm p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4">📋 Основная информация</h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Техника */}
              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Техника *
                </label>
                {loadingVehicles ? (
                  <div className="border border-gray-300 rounded-md px-3 py-2 text-gray-500">
                    Загрузка...
                  </div>
                ) : (
                  <select
                    value={vehicleId}
                    onChange={(e) => setVehicleId(e.target.value ? Number(e.target.value) : '')}
                    className="w-full border border-gray-300 rounded-md px-3 py-2"
                    required
                  >
                    <option value="">— Выберите технику —</option>
                    {vehicles.map((v) => (
                      <option key={v.id} value={v.id}>
                        🚜 {v.name}
                        {v.engine_hours ? ` (${v.engine_hours} ч)` : ''}
                        {v.status === 'maintenance' ? ' [На ТО]' : ''}
                      </option>
                    ))}
                  </select>
                )}
              </div>

              {/* Тип */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Тип *</label>
                <select
                  value={orderType}
                  onChange={(e) => setOrderType(e.target.value as MaintenanceOrderType)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2"
                >
                  {ORDER_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.icon} {t.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Плановые часы */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Плановые часы
                </label>
                <input
                  type="number"
                  step="0.5"
                  min="0"
                  value={plannedHours}
                  onChange={(e) => setPlannedHours(e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2"
                  placeholder="4.5"
                />
              </div>

              {/* Название */}
              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Название *
                </label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2"
                  placeholder="Замена тормозных колодок"
                  required
                />
              </div>

              {/* Описание */}
              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-1">Описание</label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2"
                  rows={3}
                  placeholder="Подробное описание работ..."
                />
              </div>

              {/* Симптомы */}
              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Симптомы / проблемы
                </label>
                <textarea
                  value={symptoms}
                  onChange={(e) => setSymptoms(e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2"
                  rows={2}
                  placeholder="Опишите симптомы, которые привели к созданию заказа..."
                />
              </div>
            </div>

            {/* Приоритет (карточки) */}
            <div className="mt-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">Приоритет *</label>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                {PRIORITIES.map((p) => (
                  <button
                    key={p.value}
                    type="button"
                    onClick={() => setPriority(p.value)}
                    className={`px-3 py-2 border-2 rounded-md text-sm font-medium transition-colors ${
                      priority === p.value
                        ? `${p.color} bg-gray-50`
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <div>{p.icon}</div>
                    <div>{p.label}</div>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Запчасти */}
          <div className="bg-white rounded-lg shadow-sm p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-bold text-gray-900">
                🔩 Запчасти ({parts.length})
              </h2>
              <button
                type="button"
                onClick={addPart}
                className="bg-blue-100 text-blue-700 px-3 py-1 rounded-md text-sm font-medium hover:bg-blue-200"
              >
                ➕ Добавить запчасть
              </button>
            </div>

            {parts.length === 0 ? (
              <div className="text-gray-500 text-center py-6 border-2 border-dashed border-gray-200 rounded-md">
                Запчасти не добавлены. Нажмите "➕ Добавить запчасть".
              </div>
            ) : (
              <div className="space-y-3">
                {parts.map((part, index) => (
                  <div key={index} className="border border-gray-200 rounded-md p-3">
                    <div className="grid grid-cols-1 md:grid-cols-12 gap-2">
                      <input
                        type="text"
                        placeholder="Название *"
                        value={part.name}
                        onChange={(e) => updatePart(index, 'name', e.target.value)}
                        className="md:col-span-4 border border-gray-300 rounded-md px-2 py-1 text-sm"
                      />
                      <input
                        type="text"
                        placeholder="Артикул"
                        value={part.part_number || ''}
                        onChange={(e) => updatePart(index, 'part_number', e.target.value)}
                        className="md:col-span-2 border border-gray-300 rounded-md px-2 py-1 text-sm"
                      />
                      <input
                        type="number"
                        placeholder="Кол-во"
                        min="1"
                        value={part.quantity}
                        onChange={(e) => updatePart(index, 'quantity', e.target.value)}
                        className="md:col-span-1 border border-gray-300 rounded-md px-2 py-1 text-sm"
                      />
                      <input
                        type="number"
                        placeholder="Цена"
                        min="0"
                        step="0.01"
                        value={part.unit_price}
                        onChange={(e) => updatePart(index, 'unit_price', e.target.value)}
                        className="md:col-span-2 border border-gray-300 rounded-md px-2 py-1 text-sm"
                      />
                      <div className="md:col-span-2 flex items-center justify-end text-sm font-semibold text-gray-900">
                        {formatCurrency(part.total_price || 0)}
                      </div>
                      <button
                        type="button"
                        onClick={() => removePart(index)}
                        className="md:col-span-1 text-red-600 hover:text-red-800 text-sm"
                      >
                        🗑️
                      </button>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-2">
                      <input
                        type="text"
                        placeholder="Поставщик"
                        value={part.supplier || ''}
                        onChange={(e) => updatePart(index, 'supplier', e.target.value)}
                        className="border border-gray-300 rounded-md px-2 py-1 text-sm"
                      />
                      <input
                        type="text"
                        placeholder="Заметки"
                        value={part.notes || ''}
                        onChange={(e) => updatePart(index, 'notes', e.target.value)}
                        className="border border-gray-300 rounded-md px-2 py-1 text-sm"
                      />
                    </div>
                  </div>
                ))}

                <div className="text-right text-lg font-bold text-gray-900 pt-2 border-t">
                  Итого запчасти: {formatCurrency(partsTotal)}
                </div>
              </div>
            )}
          </div>

          {/* Работы */}
          <div className="bg-white rounded-lg shadow-sm p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-bold text-gray-900">🔨 Работы ({works.length})</h2>
              <button
                type="button"
                onClick={addWork}
                className="bg-blue-100 text-blue-700 px-3 py-1 rounded-md text-sm font-medium hover:bg-blue-200"
              >
                ➕ Добавить работу
              </button>
            </div>

            {works.length === 0 ? (
              <div className="text-gray-500 text-center py-6 border-2 border-dashed border-gray-200 rounded-md">
                Работы не добавлены. Нажмите "➕ Добавить работу".
              </div>
            ) : (
              <div className="space-y-3">
                {works.map((work, index) => (
                  <div key={index} className="border border-gray-200 rounded-md p-3">
                    <div className="grid grid-cols-1 md:grid-cols-12 gap-2">
                      <input
                        type="text"
                        placeholder="Вид работы *"
                        value={work.work_type}
                        onChange={(e) => updateWork(index, 'work_type', e.target.value)}
                        className="md:col-span-4 border border-gray-300 rounded-md px-2 py-1 text-sm"
                      />
                      <input
                        type="number"
                        placeholder="Часы"
                        min="0"
                        step="0.5"
                        value={work.labor_hours}
                        onChange={(e) => updateWork(index, 'labor_hours', e.target.value)}
                        className="md:col-span-2 border border-gray-300 rounded-md px-2 py-1 text-sm"
                      />
                      <input
                        type="number"
                        placeholder="Ставка/ч"
                        min="0"
                        step="100"
                        value={work.hourly_rate}
                        onChange={(e) => updateWork(index, 'hourly_rate', e.target.value)}
                        className="md:col-span-2 border border-gray-300 rounded-md px-2 py-1 text-sm"
                      />
                      <div className="md:col-span-3 flex items-center justify-end text-sm font-semibold text-gray-900">
                        {formatCurrency(work.total_cost || 0)}
                      </div>
                      <button
                        type="button"
                        onClick={() => removeWork(index)}
                        className="md:col-span-1 text-red-600 hover:text-red-800 text-sm"
                      >
                        🗑️
                      </button>
                    </div>
                    <div className="mt-2">
                      <input
                        type="text"
                        placeholder="Описание работы"
                        value={work.description || ''}
                        onChange={(e) => updateWork(index, 'description', e.target.value)}
                        className="w-full border border-gray-300 rounded-md px-2 py-1 text-sm"
                      />
                    </div>
                  </div>
                ))}

                <div className="text-right text-lg font-bold text-gray-900 pt-2 border-t">
                  Итого работы: {formatCurrency(worksTotal)}
                </div>
              </div>
            )}
          </div>

          {/* Заметки */}
          <div className="bg-white rounded-lg shadow-sm p-6">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              📝 Дополнительные заметки
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2"
              rows={3}
              placeholder="Любые дополнительные заметки..."
            />
          </div>

          {/* Итого и кнопки */}
          <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg shadow-sm p-6 border-l-4 border-blue-600">
            <div className="flex justify-between items-center mb-4">
              <div className="text-xl font-bold text-gray-900">💰 ИТОГО:</div>
              <div className="text-3xl font-bold text-blue-700">
                {formatCurrency(grandTotal)}
              </div>
            </div>
            <div className="flex justify-between text-sm text-gray-600 mb-4">
              <span>Запчасти: {formatCurrency(partsTotal)}</span>
              <span>Работы: {formatCurrency(worksTotal)}</span>
            </div>

            <div className="flex justify-end space-x-2">
              <button
                type="button"
                onClick={() => navigate('/maintenance')}
                disabled={submitting}
                className="px-6 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 font-medium"
              >
                Отмена
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="px-6 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 font-medium disabled:opacity-50"
              >
                {submitting ? '⏳ Создаю...' : '✅ Создать наряд-заказ'}
              </button>
            </div>
          </div>
        </form>
      </div>
    </Layout>
  );
};

export default MaintenanceCreatePage;