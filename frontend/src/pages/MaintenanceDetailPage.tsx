import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Navbar } from '../components/Navbar';
import {
  getMaintenanceOrder,
  completeMaintenanceOrder,
  MaintenanceOrder,
  MaintenanceOrderStatus,
} from '../api/maintenance';
import toast from 'react-hot-toast';

const STATUS_CONFIG: Record<MaintenanceOrderStatus, { label: string; color: string; icon: string }> = {
  planned: { label: 'Запланирован', color: 'bg-blue-100 text-blue-800', icon: '📋' },
  in_progress: { label: 'В работе', color: 'bg-yellow-100 text-yellow-800', icon: '🔧' },
  completed: { label: 'Завершён', color: 'bg-green-100 text-green-800', icon: '✅' },
  cancelled: { label: 'Отменён', color: 'bg-gray-100 text-gray-600', icon: '❌' },
};

export const MaintenanceDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [order, setOrder] = useState<MaintenanceOrder | null>(null);
  const [loading, setLoading] = useState(true);

  // Модальное окно завершения
  const [showCompleteModal, setShowCompleteModal] = useState(false);
  const [actualHours, setActualHours] = useState<string>('');
  const [engineHours, setEngineHours] = useState<string>('');
  const [completeNotes, setCompleteNotes] = useState<string>('');
  const [completing, setCompleting] = useState(false);

  useEffect(() => {
    if (id) loadOrder(parseInt(id));
  }, [id]);

  const loadOrder = async (orderId: number) => {
    setLoading(true);
    try {
      const data = await getMaintenanceOrder(orderId);
      setOrder(data);
      if (data.planned_hours) {
        setActualHours(String(data.planned_hours));
      }
    } catch (error) {
      console.error('Error loading order:', error);
      toast.error('Не удалось загрузить наряд-заказ');
      navigate('/maintenance');
    } finally {
      setLoading(false);
    }
  };

  const handleComplete = async () => {
    if (!order) return;
    setCompleting(true);
    try {
      const updatedOrder = await completeMaintenanceOrder(order.id, {
        actual_hours: actualHours ? parseFloat(actualHours) : undefined,
        engine_hours_at_completion: engineHours ? parseFloat(engineHours) : undefined,
        notes: completeNotes || undefined,
      });
      toast.success('Наряд-заказ завершён!');
      setOrder(updatedOrder);
      setShowCompleteModal(false);
    } catch (error) {
      console.error('Error completing order:', error);
      toast.error('Не удалось завершить наряд-заказ');
    } finally {
      setCompleting(false);
    }
  };

  const formatCurrency = (amount: number) =>
    new Intl.NumberFormat('ru-RU', {
      style: 'currency',
      currency: 'RUB',
      minimumFractionDigits: 0,
    }).format(amount);

  const formatDateTime = (dateStr?: string) => {
    if (!dateStr) return '—';
    return new Date(dateStr).toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (loading || !order) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navbar />
        <div className="flex justify-center items-center py-20">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        </div>
      </div>
    );
  }

  const statusConfig = STATUS_CONFIG[order.status];
  const isActive = order.status === 'planned' || order.status === 'in_progress';

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-6 flex justify-between items-start flex-wrap gap-4">
          <div>
            <button
              onClick={() => navigate('/maintenance')}
              className="text-blue-600 hover:text-blue-700 text-sm mb-2"
            >
              ← Назад к списку
            </button>
            <h1 className="text-3xl font-bold text-gray-900">
              Наряд-заказ {order.order_number}
            </h1>
            <p className="text-gray-600 mt-1">{order.title}</p>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => {
                const token = localStorage.getItem('access_token');
                window.open(
                  `http://localhost:8000/api/v1/maintenance/orders/${order.id}/pdf?token=${token}`,
                  '_blank'
                );
              }}
              className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 text-sm font-medium"
            >
              📄 Наряд-заказ
            </button>

            {order.status === 'completed' && (
              <>
                <button
                  onClick={() => {
                    const token = localStorage.getItem('access_token');
                    window.open(
                      `http://localhost:8000/api/v1/maintenance/orders/${order.id}/act/pdf?token=${token}`,
                      '_blank'
                    );
                  }}
                  className="bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700 text-sm font-medium"
                >
                  📄 Акт работ
                </button>

                <button
                  onClick={async () => {
                    if (!window.confirm('Отправить акт выполненных работ клиенту по email?')) return;
                    try {
                      const response = await fetch(
                        `http://localhost:8000/api/v1/maintenance/orders/${order.id}/send-act`,
                        {
                          method: 'POST',
                          headers: {
                            Authorization: `Bearer ${localStorage.getItem('access_token')}`,
                            'Content-Type': 'application/json',
                          },
                        }
                      );
                      const data = await response.json();
                      if (response.ok) {
                        toast.success(`✅ Акт отправлен на ${data.recipient}`);
                      } else {
                        toast.error(`❌ ${data.detail || 'Ошибка отправки'}`);
                      }
                    } catch (error) {
                      toast.error('Ошибка сети при отправке email');
                    }
                  }}
                  className="bg-purple-600 text-white px-4 py-2 rounded-md hover:bg-purple-700 text-sm font-medium"
                >
                  📧 Отправить клиенту
                </button>
              </>
            )}

            {isActive && (
              <button
                onClick={() => setShowCompleteModal(true)}
                className="bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700 text-sm font-medium"
              >
                ✅ Завершить ТО
              </button>
            )}
          </div>
        </div>

        {/* Основная информация */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <div className="text-sm text-gray-500">Статус</div>
              <div className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium mt-1 ${statusConfig.color}`}>
                {statusConfig.icon} {statusConfig.label}
              </div>
            </div>
            <div>
              <div className="text-sm text-gray-500">Техника</div>
              <div className="font-medium text-gray-900 mt-1">
                🚜 {order.vehicle_name || `ID: ${order.vehicle_id}`}
              </div>
            </div>
            <div>
              <div className="text-sm text-gray-500">Приоритет</div>
              <div className="font-medium text-gray-900 mt-1 capitalize">
                {order.priority}
              </div>
            </div>

            <div>
              <div className="text-sm text-gray-500">Тип</div>
              <div className="font-medium text-gray-900 mt-1 capitalize">
                {order.order_type}
              </div>
            </div>
            <div>
              <div className="text-sm text-gray-500">Создан</div>
              <div className="font-medium text-gray-900 mt-1">
                {formatDateTime(order.created_at)}
              </div>
            </div>
            <div>
              <div className="text-sm text-gray-500">Создал</div>
              <div className="font-medium text-gray-900 mt-1">
                {order.created_by_name || `User ${order.created_by_id}`}
              </div>
            </div>

            {order.planned_hours && (
              <div>
                <div className="text-sm text-gray-500">Плановые часы</div>
                <div className="font-medium text-gray-900 mt-1">{order.planned_hours} ч</div>
              </div>
            )}
            {order.actual_hours && (
              <div>
                <div className="text-sm text-gray-500">Фактические часы</div>
                <div className="font-medium text-gray-900 mt-1">{order.actual_hours} ч</div>
              </div>
            )}
            {order.engine_hours_at_completion && (
              <div>
                <div className="text-sm text-gray-500">Моточасы при завершении</div>
                <div className="font-medium text-gray-900 mt-1">
                  {order.engine_hours_at_completion} ч
                </div>
              </div>
            )}
          </div>

          {order.description && (
            <div className="mt-4 pt-4 border-t border-gray-200">
              <div className="text-sm text-gray-500 mb-1">Описание</div>
              <div className="text-gray-900">{order.description}</div>
            </div>
          )}

          {order.notes && (
            <div className="mt-4 pt-4 border-t border-gray-200">
              <div className="text-sm text-gray-500 mb-1">Заметки</div>
              <div className="text-gray-900 whitespace-pre-wrap">{order.notes}</div>
            </div>
          )}
        </div>

        {/* Запчасти */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-bold text-gray-900">
              🔩 Запчасти ({order.parts?.length || 0})
            </h2>
            <div className="text-lg font-bold text-gray-900">
              {formatCurrency(Number(order.parts_cost))}
            </div>
          </div>

          {order.parts && order.parts.length > 0 ? (
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Название</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Артикул</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Кол-во</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Цена</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Сумма</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Поставщик</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {order.parts.map((part) => (
                  <tr key={part.id}>
                    <td className="px-4 py-2 text-sm text-gray-900">{part.name}</td>
                    <td className="px-4 py-2 text-sm text-gray-600 font-mono">{part.part_number || '—'}</td>
                    <td className="px-4 py-2 text-sm text-right">{part.quantity}</td>
                    <td className="px-4 py-2 text-sm text-right">{formatCurrency(Number(part.unit_price))}</td>
                    <td className="px-4 py-2 text-sm text-right font-semibold">{formatCurrency(Number(part.total_price))}</td>
                    <td className="px-4 py-2 text-sm text-gray-600">{part.supplier || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="text-gray-500 text-center py-4">Запчасти не добавлены</div>
          )}
        </div>

        {/* Работы */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-bold text-gray-900">
              🔨 Работы ({order.works?.length || 0})
            </h2>
            <div className="text-lg font-bold text-gray-900">
              {formatCurrency(Number(order.labor_cost))}
            </div>
          </div>

          {order.works && order.works.length > 0 ? (
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Вид работы</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Описание</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Часы</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Ставка</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Сумма</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {order.works.map((work) => (
                  <tr key={work.id}>
                    <td className="px-4 py-2 text-sm text-gray-900 font-medium">{work.work_type}</td>
                    <td className="px-4 py-2 text-sm text-gray-600">{work.description || '—'}</td>
                    <td className="px-4 py-2 text-sm text-right">{work.labor_hours} ч</td>
                    <td className="px-4 py-2 text-sm text-right">{formatCurrency(Number(work.hourly_rate))}/ч</td>
                    <td className="px-4 py-2 text-sm text-right font-semibold">{formatCurrency(Number(work.total_cost))}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="text-gray-500 text-center py-4">Работы не добавлены</div>
          )}
        </div>

        {/* Итог */}
        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg shadow-sm p-6 border-l-4 border-blue-600">
          <div className="flex justify-between items-center">
            <div className="text-xl font-bold text-gray-900">💰 ИТОГО:</div>
            <div className="text-3xl font-bold text-blue-700">
              {formatCurrency(Number(order.total_cost))}
            </div>
          </div>
          <div className="flex justify-between text-sm text-gray-600 mt-2">
            <span>Запчасти: {formatCurrency(Number(order.parts_cost))}</span>
            <span>Работы: {formatCurrency(Number(order.labor_cost))}</span>
          </div>
        </div>
      </div>

      {/* Модальное окно завершения */}
      {showCompleteModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
            <h3 className="text-xl font-bold text-gray-900 mb-4">
              ✅ Завершить наряд-заказ
            </h3>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Фактические часы работы
                </label>
                <input
                  type="number"
                  step="0.5"
                  value={actualHours}
                  onChange={(e) => setActualHours(e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2"
                  placeholder="4.5"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Моточасы техники при завершении
                </label>
                <input
                  type="number"
                  step="1"
                  value={engineHours}
                  onChange={(e) => setEngineHours(e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2"
                  placeholder="500"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Укажите текущие моточасы техники. Это обновит next_maintenance_hours.
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Заметки к завершению
                </label>
                <textarea
                  value={completeNotes}
                  onChange={(e) => setCompleteNotes(e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2"
                  rows={3}
                  placeholder="ТО завершено успешно..."
                />
              </div>
            </div>

            <div className="flex justify-end space-x-2 mt-6">
              <button
                onClick={() => setShowCompleteModal(false)}
                disabled={completing}
                className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
              >
                Отмена
              </button>
              <button
                onClick={handleComplete}
                disabled={completing}
                className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50"
              >
                {completing ? '⏳ Завершаю...' : '✅ Завершить'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default MaintenanceDetailPage;
