import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { vehiclesApi } from '../api/vehicles';
import type { Vehicle } from '../api/vehicles';
import { useAuth } from '../contexts/AuthContext';
import { VehicleFormModal } from '../components/VehicleFormModal';
import DeleteConfirmDialog from '../components/DeleteConfirmDialog';
import NotificationBell from '../components/NotificationBell';
import Layout from '../components/Layout';

export const VehiclesPage: React.FC = () => {
  const { user, logout, hasPermission } = useAuth();
  const canCreate = hasPermission('vehicles', 'create');
  const canEditVehicle = hasPermission('vehicles', 'update');
  const canDeleteVehicle = hasPermission('vehicles', 'delete');
  const navigate = useNavigate();

  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const [showFormModal, setShowFormModal] = useState(false);
  const [editingVehicle, setEditingVehicle] = useState<Vehicle | null>(null);

  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [deletingVehicle, setDeletingVehicle] = useState<Vehicle | null>(null);

  const loadVehicles = async () => {
    try {
      setIsLoading(true);
      const response = await vehiclesApi.list();
      setVehicles(response.items);
      setTotal(response.total);
      setError('');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Ошибка загрузки техники');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadVehicles();
  }, []);

  const handleCreate = () => {
    setEditingVehicle(null);
    setShowFormModal(true);
  };

  const handleEdit = (vehicle: Vehicle) => {
    setEditingVehicle(vehicle);
    setShowFormModal(true);
  };

  const handleDelete = (vehicle: Vehicle) => {
    setDeletingVehicle(vehicle);
    setShowDeleteDialog(true);
  };

  const handleFormClose = () => {
    setShowFormModal(false);
    setEditingVehicle(null);
    loadVehicles();
  };

  const handleDeleteConfirm = async () => {
    if (!deletingVehicle) return;
    try {
      await vehiclesApi.delete(deletingVehicle.id);
      setShowDeleteDialog(false);
      setDeletingVehicle(null);
      loadVehicles();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Ошибка удаления');
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'free': return 'bg-green-100 text-green-800';
      case 'busy': return 'bg-red-100 text-red-800';
      case 'maintenance': return 'bg-yellow-100 text-yellow-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'free': return 'Свободна';
      case 'busy': return 'Занята';
      case 'maintenance': return 'ТО';
      default: return status;
    }
  };

  return (
    <Layout>
      <div className="px-4 py-6 sm:px-0">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-2xl font-bold text-gray-900">
            Список техники ({total})
          </h2>
          {canCreate && (
            <button
              onClick={handleCreate}
              className="bg-blue-600 text-white px-6 py-2 rounded hover:bg-blue-700 flex items-center"
            >
              <span className="mr-2">+</span> Создать технику
            </button>
          )}
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
            {error}
          </div>
        )}

        {isLoading ? (
          <div className="text-center py-12 text-gray-500">Загрузка...</div>
        ) : vehicles.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            Техника не найдена. {canCreate && 'Создайте первую запись!'}
          </div>
        ) : (
          <div className="bg-white shadow rounded-lg overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Название</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Номер</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Категория</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Подкатегория</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Марка/Модель</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Год</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Статус</th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Действия</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {vehicles.map((vehicle) => (
                  <tr
                    key={vehicle.id}
                    // 🆕 ДОБАВЛЕНО: Клик по всей строке открывает редактирование (если есть права)
                    onClick={() => canEditVehicle && handleEdit(vehicle)}
                    // 🆕 ДОБАВЛЕНО: Визуальная подсказка, что строка кликабельна
                    className={`transition-colors ${canEditVehicle ? 'hover:bg-blue-50 cursor-pointer' : 'hover:bg-gray-50'}`}
                  >
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{vehicle.id}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{vehicle.name}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{vehicle.id_value}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {(vehicle as any).category_name || '-'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {(vehicle as any).subcategory_name || '-'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {[
                        (vehicle as any).make,
                        (vehicle as any).model,
                      ].filter(Boolean).join(' ') || '-'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{vehicle.year || '-'}</td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusColor(vehicle.status)}`}>
                        {getStatusLabel(vehicle.status)}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <div className="flex justify-end space-x-2">
                        {canEditVehicle && (
                          <button
                            // 🆕 ВАЖНО: Останавливаем всплытие события, чтобы клик по кнопке не считался кликом по строке
                            onClick={(e) => { e.stopPropagation(); handleEdit(vehicle); }}
                            className="text-blue-600 hover:text-blue-900"
                          >
                            Редактировать
                          </button>
                        )}
                        {canDeleteVehicle && (
                          <button
                            // 🆕 ВАЖНО: Останавливаем всплытие события, чтобы при удалении не открывалось окно редактирования
                            onClick={(e) => { e.stopPropagation(); handleDelete(vehicle); }}
                            className="text-red-600 hover:text-red-900"
                          >
                            Удалить
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showFormModal && (
        <VehicleFormModal
          vehicle={editingVehicle}
          onClose={handleFormClose}
        />
      )}

      {showDeleteDialog && deletingVehicle && (
        <DeleteConfirmDialog
          title="Удалить технику?"
          message={`Техника "${deletingVehicle.name}" будет удалена безвозвратно.`}
          onConfirm={handleDeleteConfirm}
          onCancel={() => {
            setShowDeleteDialog(false);
            setDeletingVehicle(null);
          }}
        />
      )}
    </Layout>
  );
};

export default VehiclesPage;