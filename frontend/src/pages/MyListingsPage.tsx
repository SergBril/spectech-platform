import React, { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import apiClient from '../api/client';

interface Vehicle {
  id: number;
  name: string;
  category_name: string;
  year: number;
  status: string;
  hourly_rate: number | null;
  shift_rate: number | null;
  is_available_for_rent: boolean;
}

export const MyListingsPage: React.FC = () => {
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState<number | null>(null);

  useEffect(() => {
    loadVehicles();
  }, []);

  const loadVehicles = async () => {
    try {
      const res = await apiClient.get('/vehicles?limit=100');
      setVehicles(Array.isArray(res.data) ? res.data : res.data?.items || []);
    } catch (e) {
      console.error('Failed to load vehicles:', e);
    } finally {
      setLoading(false);
    }
  };

  const toggleListing = async (vehicle: Vehicle) => {
    setSavingId(vehicle.id);
    try {
      await apiClient.patch(`/vehicles/${vehicle.id}`, {
        is_available_for_rent: !vehicle.is_available_for_rent,
      });
      setVehicles((prev) =>
        prev.map((v) =>
          v.id === vehicle.id
            ? { ...v, is_available_for_rent: !v.is_available_for_rent }
            : v
        )
      );
    } catch (e) {
      console.error('Failed to toggle listing:', e);
      alert('❌ Не удалось изменить статус публикации');
    } finally {
      setSavingId(null);
    }
  };

  const published = vehicles.filter((v) => v.is_available_for_rent);
  const unpublished = vehicles.filter((v) => !v.is_available_for_rent);

  if (loading) {
    return (
      <Layout>
        <div className="flex justify-center items-center py-20">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="space-y-8">
        {/* Заголовок */}
        <div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            🏪 Мои публикации на маркетплейсе
          </h1>
          <p className="text-gray-600">
            Управляйте видимостью вашей техники в каталоге
          </p>
        </div>

        {/* Статистика */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Всего техники</p>
                <p className="text-3xl font-bold text-gray-900">{vehicles.length}</p>
              </div>
              <span className="text-4xl">🚜</span>
            </div>
          </div>
          <div className="bg-green-50 rounded-lg shadow p-6 border border-green-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-green-700">Опубликовано</p>
                <p className="text-3xl font-bold text-green-900">{published.length}</p>
              </div>
              <span className="text-4xl">✅</span>
            </div>
          </div>
          <div className="bg-gray-50 rounded-lg shadow p-6 border border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Скрыто</p>
                <p className="text-3xl font-bold text-gray-900">{unpublished.length}</p>
              </div>
              <span className="text-4xl">🙈</span>
            </div>
          </div>
        </div>

        {/* Список техники */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Техника
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Категория
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Ставка
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Статус
                </th>
                <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase">
                  Публикация
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {vehicles.map((vehicle) => (
                <tr key={vehicle.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4">
                    <div className="flex items-center space-x-3">
                      <span className="text-2xl">🚜</span>
                      <div>
                        <p className="font-medium text-gray-900">{vehicle.name}</p>
                        <p className="text-sm text-gray-500">{vehicle.year} год</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">
                    {vehicle.category_name}
                  </td>
                  <td className="px-6 py-4 text-sm">
                    {vehicle.hourly_rate && (
                      <div className="text-gray-900">{vehicle.hourly_rate} ₽/час</div>
                    )}
                    {vehicle.shift_rate && (
                      <div className="text-gray-500 text-xs">
                        {vehicle.shift_rate} ₽/смена
                      </div>
                    )}
                    {!vehicle.hourly_rate && !vehicle.shift_rate && (
                      <span className="text-gray-400">—</span>
                    )}
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className={`px-2 py-1 rounded-full text-xs font-medium ${
                        vehicle.status === 'free'
                          ? 'bg-green-100 text-green-800'
                          : vehicle.status === 'busy'
                          ? 'bg-red-100 text-red-800'
                          : 'bg-yellow-100 text-yellow-800'
                      }`}
                    >
                      {vehicle.status === 'free'
                        ? 'Свободна'
                        : vehicle.status === 'busy'
                        ? 'Занята'
                        : 'На ТО'}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-center">
                    {/* Переключатель публикации */}
                    <button
                      onClick={() => toggleListing(vehicle)}
                      disabled={savingId === vehicle.id}
                      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors disabled:opacity-50 ${
                        vehicle.is_available_for_rent ? 'bg-green-500' : 'bg-gray-300'
                      }`}
                      title={
                        vehicle.is_available_for_rent
                          ? 'Снять с публикации'
                          : 'Опубликовать на маркетплейсе'
                      }
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                          vehicle.is_available_for_rent ? 'translate-x-6' : 'translate-x-1'
                        }`}
                      />
                    </button>
                    <p className="text-xs text-gray-500 mt-1">
                      {savingId === vehicle.id
                        ? 'Сохранение...'
                        : vehicle.is_available_for_rent
                        ? 'Опубликовано'
                        : 'Скрыто'}
                    </p>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>

          {vehicles.length === 0 && (
            <div className="text-center py-12">
              <p className="text-gray-500">У вас нет техники. Добавьте её в разделе "Техника".</p>
            </div>
          )}
        </div>

        {/* Подсказка */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <p className="text-sm text-blue-800">
            💡 <strong>Совет:</strong> Опубликованная техника видна всем пользователям в разделе "Маркетплейс".
            Клиенты смогут оставить заявку прямо с карточки техники.
          </p>
        </div>
      </div>
    </Layout>
  );
};

export default MyListingsPage;
