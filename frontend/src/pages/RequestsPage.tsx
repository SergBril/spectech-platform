import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { requestsApi, type Request, type RequestStatus } from '../api/requests';
import { TableSkeleton } from '../components/Skeleton';
import RequestFormModal from '../components/RequestFormModal';
import DeleteConfirmDialog from '../components/DeleteConfirmDialog';
import NotificationBell from '../components/NotificationBell';
import Navbar from '../components/Navbar';

const STATUS_LABELS: Record<RequestStatus, { label: string; color: string }> = {
  new: { label: 'Новая', color: 'bg-blue-100 text-blue-800' },
  processing: { label: 'В обработке', color: 'bg-yellow-100 text-yellow-800' },
  assigned: { label: 'Назначена', color: 'bg-indigo-100 text-indigo-800' },
  confirmed: { label: 'Подтверждена', color: 'bg-green-100 text-green-800' },
  released: { label: 'Выпущена', color: 'bg-purple-100 text-purple-800' },
  in_progress: { label: 'В работе', color: 'bg-cyan-100 text-cyan-800' },
  completed: { label: 'Завершена', color: 'bg-emerald-100 text-emerald-800' },
  signed: { label: 'Подписана', color: 'bg-teal-100 text-teal-800' },
  closed: { label: 'Закрыта', color: 'bg-gray-100 text-gray-800' },
  cancelled: { label: 'Отменена', color: 'bg-red-100 text-red-800' },
  disputed: { label: 'Спорная', color: 'bg-orange-100 text-orange-800' },
};

const PRIORITY_LABELS: Record<string, { label: string; color: string }> = {
  low: { label: 'Низкий', color: 'text-gray-600' },
  normal: { label: 'Обычный', color: 'text-blue-600' },
  high: { label: 'Высокий', color: 'text-orange-600' },
  urgent: { label: 'Срочный', color: 'text-red-600 font-semibold' },
};

const formatDateTime = (dt: string | null) => {
  if (!dt) return '—';
  return new Date(dt).toLocaleString('ru-RU', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit'
  });
};

const formatMoney = (v: number | string | null | undefined) => {
  if (v === null || v === undefined || v === '') return '—';
  const num = typeof v === 'string' ? parseFloat(v) : v;
  return `${num.toLocaleString('ru-RU')} ₽`;
};

export const RequestsPage: React.FC = () => {
  const { user, logout, hasPermission } = useAuth();
  const navigate = useNavigate();

  const [requests, setRequests] = useState<Request[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingRequest, setEditingRequest] = useState<Request | null>(null);

  const [deleteTarget, setDeleteTarget] = useState<Request | null>(null);

  const canCreate = hasPermission('requests', 'create');
  const canEdit = hasPermission('requests', 'update');
  const canDelete = hasPermission('requests', 'delete');

  const loadRequests = async () => {
    try {
      setLoading(true);
      const data = await requestsApi.getAll({ limit: 100 });
      setRequests(data);
      setError('');
    } catch (err: any) {
      console.error('Failed to load requests:', err);
      setError('Не удалось загрузить заявки');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRequests();
  }, []);

  const handleCreate = () => {
    setEditingRequest(null);
    setIsModalOpen(true);
  };

  const handleEdit = (request: Request) => {
    setEditingRequest(request);
    setIsModalOpen(true);
  };

  const handleDelete = (request: Request) => {
    setDeleteTarget(request);
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    try {
      await requestsApi.delete(deleteTarget.id);
      setRequests(requests.filter(r => r.id !== deleteTarget.id));
      setDeleteTarget(null);
    } catch (err: any) {
      console.error('Failed to delete request:', err);
      alert('Ошибка при удалении заявки');
    }
  };

  const handleSave = async (data: any) => {
    try {
      if (editingRequest) {
        const updated = await requestsApi.update(editingRequest.id, data);
        setRequests(requests.map(r => r.id === editingRequest.id ? updated : r));
      } else {
        const created = await requestsApi.create(data);
        setRequests([created, ...requests]);
      }
      setIsModalOpen(false);
      setEditingRequest(null);
    } catch (err: any) {
      console.error('Failed to save request:', err);
      alert('Ошибка при сохранении: ' + (err?.response?.data?.detail || err.message));
      throw err;
    }
  };

if (loading) {
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navbar */}
      <Navbar />

      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          {/* Skeleton заголовка + кнопки */}
          <div className="flex justify-between items-center mb-6">
            <div className="w-40 h-8 bg-gray-200 rounded animate-pulse" />
            <div className="w-40 h-10 bg-gray-200 rounded animate-pulse" />
          </div>

          {/* Skeleton фильтров */}
          <div className="bg-white rounded-lg shadow p-4 mb-6 animate-pulse">
            <div className="flex flex-wrap gap-3">
              <div className="w-48 h-10 bg-gray-100 rounded" />
              <div className="w-40 h-10 bg-gray-100 rounded" />
              <div className="w-40 h-10 bg-gray-100 rounded" />
            </div>
          </div>

          {/* Skeleton таблицы заявок */}
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <TableSkeleton rows={8} columns={8} />
          </div>
        </div>
      </main>
    </div>
  );
}

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold text-gray-900">
              Список заявок ({requests.length})
            </h2>
            {canCreate && (
              <button
                onClick={handleCreate}
                className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 flex items-center"
              >
                <span className="mr-2">+</span> Новая заявка
              </button>
            )}
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-6">
              {error}
            </div>
          )}

          <div className="bg-white shadow rounded-lg overflow-hidden">
            {requests.length === 0 ? (
              <div className="p-12 text-center text-gray-500">
                <div className="text-5xl mb-4">📋</div>
                <p className="text-lg">Заявок пока нет</p>
                {canCreate && (
                  <p className="mt-2">Создайте первую заявку, нажав кнопку выше</p>
                )}
              </div>
            ) : (
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Тип работы</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Адрес объекта</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Период</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Статус</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Приоритет</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Сумма</th>
                    {(canEdit || canDelete) && (
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Действия</th>
                    )}
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {requests.map((req) => (
                    <tr key={req.id} className="hover:bg-gray-50">
                      <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900 font-mono">
                        <button
                          onClick={() => navigate(`/requests/${req.id}`)}
                          className="text-blue-600 hover:text-blue-900 hover:underline font-medium"
                          title="Открыть детали заявки"
                        >
                          #{req.id}
                        </button>
                      </td>
                      <td className="px-4 py-4 text-sm text-gray-900">
                        <div className="font-medium">{req.work_type || '—'}</div>
                        <div className="text-xs text-gray-500">{req.request_type}</div>
                      </td>
                      <td className="px-4 py-4 text-sm text-gray-600 max-w-xs truncate">
                        {req.object_address || '—'}
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap text-xs text-gray-600">
                        <div>{formatDateTime(req.planned_start)}</div>
                        <div>— {formatDateTime(req.planned_end)}</div>
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap">
                        <span className={`px-2 py-1 text-xs font-semibold rounded-full ${STATUS_LABELS[req.status]?.color || 'bg-gray-100'}`}>
                          {STATUS_LABELS[req.status]?.label || req.status}
                        </span>
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap text-sm">
                        <span className={PRIORITY_LABELS[req.priority]?.color || 'text-gray-600'}>
                          {PRIORITY_LABELS[req.priority]?.label || req.priority}
                        </span>
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900">
                        {formatMoney(req.estimated_amount)}
                      </td>
                      {(canEdit || canDelete) && (
                        <td className="px-4 py-4 whitespace-nowrap text-right text-sm font-medium space-x-2">
                          {canEdit && (
                            <button
                              onClick={() => handleEdit(req)}
                              className="text-blue-600 hover:text-blue-900"
                            >
                              Редактировать
                            </button>
                          )}
                          {canDelete && (
                            <button
                              onClick={() => handleDelete(req)}
                              className="text-red-600 hover:text-red-900"
                            >
                              Удалить
                            </button>
                          )}
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </main>

      {isModalOpen && (
        <RequestFormModal
          request={editingRequest}
          onClose={() => { setIsModalOpen(false); setEditingRequest(null); }}
          onSave={handleSave}
        />
      )}

      {deleteTarget && (
        <DeleteConfirmDialog
          title="Удалить заявку?"
          message={`Вы уверены, что хотите удалить заявку #${deleteTarget.id} "${deleteTarget.work_type}"?`}
          onConfirm={confirmDelete}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
};

export default RequestsPage;
