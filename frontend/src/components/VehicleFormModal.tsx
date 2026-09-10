import React, { useState } from 'react';
import { vehiclesApi } from '../api/vehicles';
import type { Vehicle, VehicleCreate } from '../api/vehicles';

interface VehicleFormModalProps {
  vehicle: Vehicle | null;
  onClose: () => void;
}

export const VehicleFormModal: React.FC<VehicleFormModalProps> = ({ vehicle, onClose }) => {
  const isEdit = !!vehicle;

  const [formData, setFormData] = useState<VehicleCreate>({
    id_type: vehicle?.id_type || 'license_plate',
    id_value: vehicle?.id_value || '',
    name: vehicle?.name || '',
    year: vehicle?.year || undefined,
    status: vehicle?.status || 'free',
    fuel_norm_per_hour: vehicle?.fuel_norm_per_hour ? parseFloat(vehicle.fuel_norm_per_hour) : undefined,
    fuel_norm_per_100km: vehicle?.fuel_norm_per_100km ? parseFloat(vehicle.fuel_norm_per_100km) : undefined,
  });

  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      if (isEdit && vehicle) {
        await vehiclesApi.update(vehicle.id, formData);
      } else {
        await vehiclesApi.create(formData);
      }
      onClose();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Ошибка сохранения');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="px-6 py-4 border-b">
          <h2 className="text-xl font-bold">
            {isEdit ? 'Редактировать технику' : 'Создать технику'}
          </h2>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Тип ID *</label>
              <select
                value={formData.id_type}
                onChange={(e) => setFormData({ ...formData, id_type: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded"
                required
              >
                <option value="license_plate">Гос. номер</option>
                <option value="VIN">VIN</option>
                <option value="inventory">Инвентарный номер</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Номер *</label>
              <input
                type="text"
                value={formData.id_value}
                onChange={(e) => setFormData({ ...formData, id_value: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded"
                required
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Название *</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Год</label>
              <input
                type="number"
                value={formData.year || ''}
                onChange={(e) => setFormData({ ...formData, year: parseInt(e.target.value) || undefined })}
                className="w-full px-3 py-2 border border-gray-300 rounded"
                min="1900"
                max="2100"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Статус *</label>
              <select
                value={formData.status}
                onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded"
                required
              >
                <option value="free">Свободна</option>
                <option value="busy">Занята</option>
                <option value="maintenance">ТО</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Расход (л/час)</label>
              <input
                type="number"
                step="0.01"
                value={formData.fuel_norm_per_hour || ''}
                onChange={(e) => setFormData({ ...formData, fuel_norm_per_hour: parseFloat(e.target.value) || undefined })}
                className="w-full px-3 py-2 border border-gray-300 rounded"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Расход (л/100км)</label>
              <input
                type="number"
                step="0.01"
                value={formData.fuel_norm_per_100km || ''}
                onChange={(e) => setFormData({ ...formData, fuel_norm_per_100km: parseFloat(e.target.value) || undefined })}
                className="w-full px-3 py-2 border border-gray-300 rounded"
              />
            </div>
          </div>

          <div className="flex justify-end space-x-3 pt-4 border-t">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 rounded hover:bg-gray-50"
            >
              Отмена
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {isLoading ? 'Сохранение...' : isEdit ? 'Сохранить' : 'Создать'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
