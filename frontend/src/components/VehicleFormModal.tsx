import React, { useState, useEffect } from 'react';
import { vehiclesApi } from '../api/vehicles';
import type { Vehicle, VehicleCreate } from '../api/vehicles';
import { EquipmentSelector } from './EquipmentSelector';
import GpsProviderSelector from './GpsProviderSelector';

interface VehicleFormModalProps {
  vehicle: Vehicle | null;
  onClose: () => void;
}

export const VehicleFormModal: React.FC<VehicleFormModalProps> = ({ vehicle, onClose }) => {
  const isEdit = !!vehicle;

  const [formData, setFormData] = useState<VehicleCreate & {
    make?: string;
    model?: string;
    vin?: string;
    category_id?: number;
    subcategory_id?: number;
    attributes?: Record<string, any>;
  }>({
    id_type: vehicle?.id_type || 'license_plate',
    id_value: vehicle?.id_value || '',
    name: vehicle?.name || '',
    year: vehicle?.year || undefined,
    status: vehicle?.status || 'free',
    fuel_norm_per_hour: vehicle?.fuel_norm_per_hour ? parseFloat(vehicle.fuel_norm_per_hour as any) : undefined,
    fuel_norm_per_100km: vehicle?.fuel_norm_per_100km ? parseFloat(vehicle.fuel_norm_per_100km as any) : undefined,
    make: (vehicle as any)?.make || '',
    model: (vehicle as any)?.model || '',
    vin: (vehicle as any)?.vin || '',
    category_id: (vehicle as any)?.category_id || undefined,
    subcategory_id: (vehicle as any)?.subcategory_id || undefined,
    attributes: (vehicle as any)?.attributes || {},
  });

  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [gpsProvider, setGpsProvider] = useState<{ provider: string; config: Record<string, any> } | null>(null);

  // Загрузка GPS-провайдера при редактировании
  useEffect(() => {
    if (vehicle && (vehicle as any).gps_provider) {
      setGpsProvider({
        provider: (vehicle as any).gps_provider,
        config: (vehicle as any).gps_provider_config || {},
      });
    } else {
      setGpsProvider(null);
    }
  }, [vehicle]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      // Подготавливаем данные для отправки
      const payload: any = {
        ...formData,
        // Очищаем пустые строки
        make: formData.make || null,
        model: formData.model || null,
        vin: formData.vin || null,
        // GPS-провайдер
        gps_provider: gpsProvider?.provider || null,
        gps_provider_config: gpsProvider?.config || null,
        marketplace_commission_agreed: (document.getElementById('commission-agreed') as HTMLInputElement)?.checked || false,
        marketplace_commission_rate: 10.00,
      };

      if (isEdit && vehicle) {
        await vehiclesApi.update(vehicle.id, payload);
      } else {
        await vehiclesApi.create(payload);
      }
      onClose();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Ошибка сохранения');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[90vh] overflow-y-auto">
        <div className="px-6 py-4 border-b sticky top-0 bg-white z-10">
          <h2 className="text-xl font-bold">
            {isEdit ? 'Редактировать технику' : 'Создать технику'}
          </h2>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}

          {/* === ОСНОВНЫЕ ДАННЫЕ === */}
          <div className="border-b pb-4">
            <h3 className="text-sm font-semibold text-gray-900 mb-3">🚗 Основные данные</h3>

            <div className="grid grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Тип ID *</label>
                <select
                  value={formData.id_type}
                  onChange={(e) => setFormData({ ...formData, id_type: e.target.value as any })}
                  className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
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
                  className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="А123БВ777 / XTA..."
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
                className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Например: Экскаватор CAT 320D"
                required
              />
            </div>
          </div>

          {/* === КАТАЛОГ ТЕХНИКИ === */}
          <div className="border-b pb-4">
            <h3 className="text-sm font-semibold text-gray-900 mb-3">📋 Каталог техники</h3>
            <EquipmentSelector
              value={{
                category_id: formData.category_id,
                subcategory_id: formData.subcategory_id,
                attributes: formData.attributes,
              }}
              onChange={(data) =>
                setFormData({
                  ...formData,
                  category_id: data.category_id,
                  subcategory_id: data.subcategory_id,
                  attributes: data.attributes,
                })
              }
            />
          </div>

          {/* === МАРКА, МОДЕЛЬ, VIN === */}
          <div className="border-b pb-4">
            <h3 className="text-sm font-semibold text-gray-900 mb-3">🔍 Идентификация (для поиска запчастей)</h3>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Марка</label>
                <input
                  type="text"
                  value={formData.make || ''}
                  onChange={(e) => setFormData({ ...formData, make: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="CAT, Komatsu"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Модель</label>
                <input
                  type="text"
                  value={formData.model || ''}
                  onChange={(e) => setFormData({ ...formData, model: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="320D, PC200"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">VIN</label>
                <input
                  type="text"
                  value={formData.vin || ''}
                  onChange={(e) => setFormData({ ...formData, vin: e.target.value.toUpperCase() })}
                  className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="17 символов"
                  maxLength={17}
                />
              </div>
            </div>
          </div>

          {/* === 📡 GPS-ПРОВАЙДЕР === */}
          <div className="border-b pb-4">
            <h3 className="text-sm font-semibold text-gray-900 mb-3">📡 GPS-мониторинг</h3>
            <GpsProviderSelector
              value={gpsProvider}
              onChange={setGpsProvider}
            />
          </div>

          {/* === СТАТУС И ГОД === */}
          <div className="border-b pb-4">
            <h3 className="text-sm font-semibold text-gray-900 mb-3">⚙️ Статус и параметры</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Год выпуска</label>
                <input
                  type="number"
                  value={formData.year || ''}
                  onChange={(e) => setFormData({ ...formData, year: parseInt(e.target.value) || undefined })}
                  className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  min="1900"
                  max="2100"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Статус *</label>
                <select
                  value={formData.status}
                  onChange={(e) => setFormData({ ...formData, status: e.target.value as any })}
                  className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  required
                >
                  <option value="free">Свободна</option>
                  <option value="busy">Занята</option>
                  <option value="maintenance">ТО</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 mt-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Расход (л/час)</label>
                <input
                  type="number"
                  step="0.01"
                  value={formData.fuel_norm_per_hour || ''}
                  onChange={(e) => setFormData({ ...formData, fuel_norm_per_hour: parseFloat(e.target.value) || undefined })}
                  className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Расход (л/100км)</label>
                <input
                  type="number"
                  step="0.01"
                  value={formData.fuel_norm_per_100km || ''}
                  onChange={(e) => setFormData({ ...formData, fuel_norm_per_100km: parseFloat(e.target.value) || undefined })}
                  className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>
          </div>

          {/* === КНОПКИ === */}
          <div className="flex justify-end space-x-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isLoading}
              className="px-4 py-2 border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50"
            >
              Отмена
            </button>
            {/* Marketplace Commission Agreement */}
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
              <div className="flex items-start gap-3">
                <span className="text-2xl">⚠️</span>
                <div className="flex-1">
                  <h4 className="font-semibold text-amber-900 mb-1">Комиссия маркетплейса</h4>
                  <p className="text-sm text-amber-800 mb-2">
                    Выставляя стоимость техники, вы даёте согласие на комиссию <b>10%</b> от стоимости заказа 
                    в случаях, когда заказ поступает через маркетплейс платформы. 
                    Комиссия не взимается за прямые заказы.
                  </p>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      id="commission-agreed"
                      defaultChecked={(vehicle as any)?.marketplace_commission_agreed || false}
                      className="w-4 h-4 rounded border-amber-300 text-amber-600 focus:ring-amber-500"
                    />
                    <span className="text-sm font-medium text-amber-900">
                      Я согласен с условиями комиссии маркетплейса (10%)
                    </span>
                  </label>
                </div>
              </div>
            </div>

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