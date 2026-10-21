import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Layout from '../components/Layout'; // Layout уже здесь
import { getVehicleTCO, VehicleTCO } from '../api/maintenance';
import toast from 'react-hot-toast';
import apiClient from '../api/client';

export const MaintenanceAnalyticsPage: React.FC = () => {
  const navigate = useNavigate();
  const [vehicles, setVehicles] = useState<{ id: number; name: string }[]>([]);
  const [selectedVehicleId, setSelectedVehicleId] = useState<number | ''>('');
  const [tcoData, setTcoData] = useState<VehicleTCO | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadVehicles();
  }, []);

  useEffect(() => {
    if (selectedVehicleId) {
      loadTCO(Number(selectedVehicleId));
    }
  }, [selectedVehicleId]);

  const loadVehicles = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const companyId = localStorage.getItem('spectech_current_company_id');
      const response = await fetch(`http://localhost:8000/api/v1/vehicles?limit=100`, {
        headers: {
          Authorization: `Bearer ${token}`,
          'X-Company-Id': companyId || '',
        },
      });
      if (response.ok) {
        const data = await response.json();
        setVehicles(data.items || data);
        if (data.items?.length > 0) setSelectedVehicleId(data.items[0].id);
      }
    } catch (error) {
      toast.error('Не удалось загрузить список техники');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  };

  const loadTCO = async (vehicleId: number) => {
    setLoading(true);
    try {
      const data = await getVehicleTCO(vehicleId);
      setTcoData(data);
    } catch (error) {
      console.error(error);
      toast.error('Не удалось загрузить данные TCO');
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (amount: number) =>
    new Intl.NumberFormat('ru-RU', {
      style: 'currency',
      currency: 'RUB',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);

  // ИСПРАВЛЕНО: Убран Navbar, всё содержимое обернуто в Layout
  return (
    <Layout>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <button
            onClick={() => navigate('/maintenance')}
            className="text-blue-600 hover:text-blue-700 text-sm mb-2"
          >
            ← Назад к наряд-заказам
          </button>
          <h1 className="text-3xl font-bold text-gray-900">📊 Аналитика TCO (Стоимость владения)</h1>
          <p className="text-gray-600 mt-1">
            Расчёт полных затрат на эксплуатацию техники: ТО, ремонты и топливо.
          </p>
        </div>

        {/* Выбор техники */}
        <div className="bg-white rounded-lg shadow-sm p-4 mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">Выберите технику для анализа:</label>
          <select
            value={selectedVehicleId}
            onChange={(e) => setSelectedVehicleId(e.target.value ? Number(e.target.value) : '')}
            className="w-full md:w-1/2 border border-gray-300 rounded-md px-3 py-2"
          >
            <option value="">— Выберите технику —</option>
            {vehicles.map((v) => (
              <option key={v.id} value={v.id}>
                🚜 {v.name}
              </option>
            ))}
          </select>
        </div>

        {loading ? (
          <div className="flex justify-center items-center py-20">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
          </div>
        ) : tcoData ? (
          <div className="space-y-6">
            {/* Главные метрики */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="bg-gradient-to-br from-blue-500 to-blue-600 rounded-lg shadow-md p-6 text-white">
                <div className="text-blue-100 text-sm font-medium mb-1">💰 Общий TCO</div>
                <div className="text-3xl font-bold">{formatCurrency(tcoData.total_tco)}</div>
                <div className="text-blue-100 text-xs mt-2">Сумма всех затрат за всё время</div>
              </div>

              <div className="bg-gradient-to-br from-indigo-500 to-indigo-600 rounded-lg shadow-md p-6 text-white">
                <div className="text-indigo-100 text-sm font-medium mb-1">⏱️ Стоимость 1 моточаса</div>
                <div className="text-3xl font-bold">{formatCurrency(tcoData.cost_per_hour)}</div>
                <div className="text-indigo-100 text-xs mt-2">Средние затраты в час работы</div>
              </div>

              <div className="bg-gradient-to-br from-gray-700 to-gray-800 rounded-lg shadow-md p-6 text-white">
                <div className="text-gray-300 text-sm font-medium mb-1">⏳ Наработка</div>
                <div className="text-3xl font-bold">{tcoData.engine_hours.toFixed(1)} ч</div>
                <div className="text-gray-300 text-xs mt-2">Текущие моточасы техники</div>
              </div>
            </div>

            {/* Детализация затрат */}
            <div className="bg-white rounded-lg shadow-sm p-6">
              <h2 className="text-lg font-bold text-gray-900 mb-4">📉 Структура затрат</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="border border-gray-200 rounded-lg p-4">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-gray-600 font-medium">🔧 ТО и Ремонты</span>
                    <span className="text-xl font-bold text-gray-900">{formatCurrency(tcoData.maintenance_cost)}</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2.5">
                    <div
                      className="bg-blue-600 h-2.5 rounded-full"
                      style={{ width: `${tcoData.total_tco > 0 ? (tcoData.maintenance_cost / tcoData.total_tco) * 100 : 0}%` }}
                    ></div>
                  </div>
                  <div className="text-xs text-gray-500 mt-1 text-right">
                    {tcoData.total_tco > 0 ? Math.round((tcoData.maintenance_cost / tcoData.total_tco) * 100) : 0}% от общих затрат
                  </div>
                </div>

                <div className="border border-gray-200 rounded-lg p-4">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-gray-600 font-medium">⛽ Топливо</span>
                    <span className="text-xl font-bold text-gray-900">{formatCurrency(tcoData.fuel_cost)}</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2.5">
                    <div
                      className="bg-yellow-500 h-2.5 rounded-full"
                      style={{ width: `${tcoData.total_tco > 0 ? (tcoData.fuel_cost / tcoData.total_tco) * 100 : 0}%` }}
                    ></div>
                  </div>
                  <div className="text-xs text-gray-500 mt-1 text-right">
                    {tcoData.total_tco > 0 ? Math.round((tcoData.fuel_cost / tcoData.total_tco) * 100) : 0}% от общих затрат
                  </div>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="bg-white rounded-lg shadow-sm p-12 text-center text-gray-500">
            Выберите технику, чтобы увидеть аналитику TCO.
          </div>
        )}
      </div>
    </Layout>
  );
};

export default MaintenanceAnalyticsPage;