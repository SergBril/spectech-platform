import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Layout from '../components/Layout'; // <-- ДОБАВЛЕНО
import {
  listMaintenanceOrders,
  checkScheduledMaintenance,
  MaintenanceOrder,
  MaintenanceOrderStatus,
  MaintenanceOrderType,
  MaintenancePriority,
} from '../api/maintenance';
import toast from 'react-hot-toast';

// === Константы для UI ===

const STATUS_CONFIG: Record<MaintenanceOrderStatus, { label: string; color: string; icon: string }> = {
  planned: { label: 'Запланирован', color: 'bg-blue-100 text-blue-800', icon: '📋' },
  in_progress: { label: 'В работе', color: 'bg-yellow-100 text-yellow-800', icon: '🔧' },
  completed: { label: 'Завершён', color: 'bg-green-100 text-green-800', icon: '✅' },
  cancelled: { label: 'Отменён', color: 'bg-gray-100 text-gray-600', icon: '❌' },
};

const PRIORITY_CONFIG: Record<MaintenancePriority, { label: string; color: string; icon: string }> = {
  low: { label: 'Низкий', color: 'bg-gray-100 text-gray-600', icon: '🟢' },
  medium: { label: 'Средний', color: 'bg-blue-100 text-blue-700', icon: '🟡' },
  high: { label: 'Высокий', color: 'bg-orange-100 text-orange-700', icon: '🟠' },
  critical: { label: 'Критичный', color: 'bg-red-100 text-red-700', icon: '🔴' },
};

const TYPE_CONFIG: Record<MaintenanceOrderType, { label: string; icon: string }> = {
  scheduled: { label: 'Плановое ТО', icon: '🔧' },
  repair: { label: 'Ремонт', icon: '🛠️' },
  diagnostic: { label: 'Диагностика', icon: '🔍' },
  inspection: { label: 'Осмотр', icon: '👁️' },
};

export const MaintenancePage: React.FC = () => {
  const navigate = useNavigate();
  const [orders, setOrders] = useState<MaintenanceOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);

  // Фильтры
  const [statusFilter, setStatusFilter] = useState<MaintenanceOrderStatus | ''>('');
  const [typeFilter, setTypeFilter] = useState<MaintenanceOrderType | ''>('');
  const [priorityFilter, setPriorityFilter] = useState<MaintenancePriority | ''>('');

  // Статистика
  const [stats, setStats] = useState({
    planned: 0,
    in_progress: 0,
    completed: 0,
    total_cost: 0,
  });

  useEffect(() => {
    loadOrders();
  }, [statusFilter, typeFilter, priorityFilter]);

  const loadOrders = async () => {
    setLoading(true);
    try {
      const response = await listMaintenanceOrders({
        status: statusFilter || undefined,
        order_type: typeFilter || undefined,
        priority: priorityFilter || undefined,
        limit: 200,
      });

      setOrders(response.items);

      // Подсчёт статистики
      const statsCalc = {
        planned: 0,
        in_progress: 0,
        completed: 0,
        total_cost: 0,
      };

      response.items.forEach((order) => {
        if (order.status === 'planned') statsCalc.planned++;
        if (order.status === 'in_progress') statsCalc.in_progress++;
        if (order.status === 'completed') statsCalc.completed++;
        statsCalc.total_cost += Number(order.total_cost);
      });

      setStats(statsCalc);
    } catch (error) {
      console.error('Error loading orders:', error);
      toast.error('Не удалось загрузить наряд-заказы');
    } finally {
      setLoading(false);
    }
  };

  const handleCheckScheduled = async () => {
    setChecking(true);
    try {
      const result = await checkScheduledMaintenance();

      if (result.created_count > 0) {
        toast.success(
          `Создано ${result.created_count} наряд-заказ(ов) на плановое ТО!`,
          { duration: 5000 }
        );
        loadOrders();
      } else {
        toast.success('Все плановые ТО актуальны!', { icon: '✅' });
      }
    } catch (error) {
      console.error('Error checking scheduled:', error);
      toast.error('Ошибка при проверке плановых ТО');
    } finally {
      setChecking(false);
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('ru-RU', {
      style: 'currency',
      currency: 'RUB',
      minimumFractionDigits: 0,
    }).format(amount);
  };

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '—';
    return new Date(dateStr).toLocaleDateString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });
  };

  // ИСПРАВЛЕНО: Обертка загрузки в Layout
  if (loading && orders.length === 0) {
    return (
      <Layout>
        <div className="flex justify-center items-center py-20">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        </div>
      </Layout>
    );
  }

  // ИСПРАВЛЕНО: Убран Navbar, всё обернуто в Layout
  return (
    <Layout>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Заголовок */}
        <div className="mb-8 flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">🔧 ТО и Ремонты</h1>
            <p className="text-gray-600 mt-1">
              Управление наряд-заказами на техническое обслуживание
            </p>
          </div>
          <div className="flex space-x-2">
            <button
              onClick={handleCheckScheduled}
              disabled={checking}
              className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 text-sm font-medium disabled:opacity-50"
            >
              {checking ? '⏳ Проверяю...' : '🔍 Проверить плановые ТО'}
            </button>
            <button
              onClick={() => navigate('/maintenance/new')}
              className="bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700 text-sm font-medium"
            >
              ➕ Создать наряд-заказ
            </button>
            <button
              onClick={() => navigate('/maintenance/analytics')}
              className="bg-purple-600 text-white px-4 py-2 rounded-md hover:bg-purple-700 text-sm font-medium"
            >
              📊 Аналитика TCO
            </button>
          </div>
        </div>

        {/* Статистика */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-white rounded-lg shadow-sm p-4 border-l-4 border-blue-500">
            <div className="text-gray-600 text-sm">📋 Запланировано</div>
            <div className="text-2xl font-bold text-gray-900">{stats.planned}</div>
          </div>
          <div className="bg-white rounded-lg shadow-sm p-4 border-l-4 border-yellow-500">
            <div className="text-gray-600 text-sm">🔧 В работе</div>
            <div className="text-2xl font-bold text-gray-900">{stats.in_progress}</div>
          </div>
          <div className="bg-white rounded-lg shadow-sm p-4 border-l-4 border-green-500">
            <div className="text-gray-600 text-sm">✅ Завершено</div>
            <div className="text-2xl font-bold text-gray-900">{stats.completed}</div>
          </div>
          <div className="bg-white rounded-lg shadow-sm p-4 border-l-4 border-purple-500">
            <div className="text-gray-600 text-sm">💰 Общая стоимость</div>
            <div className="text-2xl font-bold text-gray-900">
              {formatCurrency(stats.total_cost)}
            </div>
          </div>
        </div>

        {/* Фильтры */}
        <div className="bg-white rounded-lg shadow-sm p-4 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Статус</label>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as MaintenanceOrderStatus | '')}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
              >
                <option value="">Все статусы</option>
                {Object.entries(STATUS_CONFIG).map(([key, config]) => (
                  <option key={key} value={key}>
                    {config.icon} {config.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Тип</label>
              <select
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value as MaintenanceOrderType | '')}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
              >
                <option value="">Все типы</option>
                {Object.entries(TYPE_CONFIG).map(([key, config]) => (
                  <option key={key} value={key}>
                    {config.icon} {config.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Приоритет</label>
              <select
                value={priorityFilter}
                onChange={(e) => setPriorityFilter(e.target.value as MaintenancePriority | '')}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
              >
                <option value="">Все приоритеты</option>
                {Object.entries(PRIORITY_CONFIG).map(([key, config]) => (
                  <option key={key} value={key}>
                    {config.icon} {config.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Список наряд-заказов */}
        {orders.length === 0 ? (
          <div className="bg-white rounded-lg shadow-sm p-12 text-center">
            <div className="text-6xl mb-4">📋</div>
            <h3 className="text-xl font-semibold text-gray-900 mb-2">
              Нет наряд-заказов
            </h3>
            <p className="text-gray-600 mb-4">
              Создайте первый наряд-заказ или проверьте плановые ТО
            </p>
            <button
              onClick={() => navigate('/maintenance/new')}
              className="bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700"
            >
              ➕ Создать наряд-заказ
            </button>
          </div>
        ) : (
          <div className="bg-white rounded-lg shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Номер
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Техника
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Тип
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Название
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Статус
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Приоритет
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Стоимость
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Дата
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {orders.map((order) => {
                  const statusConfig = STATUS_CONFIG[order.status];
                  const priorityConfig = PRIORITY_CONFIG[order.priority];
                  const typeConfig = TYPE_CONFIG[order.order_type];

                  return (
                    <tr
                      key={order.id}
                      onClick={() => navigate(`/maintenance/${order.id}`)}
                      className="hover:bg-gray-50 cursor-pointer transition-colors"
                    >
                      <td className="px-4 py-3 text-sm font-mono text-blue-600">
                        {order.order_number}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900">
                        🚜 {order.vehicle_name || `ID: ${order.vehicle_id}`}
                      </td>
                      <td className="px-4 py-3 text-sm">
                        <span className="text-gray-700">
                          {typeConfig.icon} {typeConfig.label}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm font-medium text-gray-900 max-w-xs truncate">
                        {order.title}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${statusConfig.color}`}
                        >
                          {statusConfig.icon} {statusConfig.label}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${priorityConfig.color}`}
                        >
                          {priorityConfig.icon} {priorityConfig.label}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm text-right font-semibold text-gray-900">
                        {formatCurrency(Number(order.total_cost))}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        {formatDate(order.created_at)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default MaintenancePage;
