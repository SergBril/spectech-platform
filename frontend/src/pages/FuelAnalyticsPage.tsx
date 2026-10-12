import React, { useEffect, useState } from 'react';
import Layout from '../components/Layout'; // Layout уже здесь, мы его используем
import {
  getFuelAnalytics,
  getFuelConsumption,
  getFuelByVehicle,
  FuelAnalytics,
  ConsumptionRate,
  FuelByVehicle,
} from '../api/fuel';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { getFuelAnomalies, FuelAnomaly } from '../api/fuel';
import { FuelAnomalyAlerts } from '../components/FuelAnomalyAlerts';

export const FuelAnalyticsPage: React.FC = () => {
  const [analytics, setAnalytics] = useState<FuelAnalytics | null>(null);
  const [consumption, setConsumption] = useState<ConsumptionRate[]>([]);
  const [byVehicle, setByVehicle] = useState<FuelByVehicle[]>([]);
  const [anomalies, setAnomalies] = useState<FuelAnomaly[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [analyticsData, consumptionData, byVehicleData, anomaliesData] = await Promise.all([
        getFuelAnalytics(),
        getFuelConsumption(),
        getFuelByVehicle(),
        getFuelAnomalies(),
      ]);
      setAnalytics(analyticsData);
      setConsumption(consumptionData);
      setAnomalies(anomaliesData.anomalies);
      setByVehicle(byVehicleData);
    } catch (error) {
      console.error('Error loading fuel analytics:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('ru-RU', {
      style: 'currency',
      currency: 'RUB',
      minimumFractionDigits: 0,
    }).format(value);
  };

  const formatVolume = (value: number) => `${value} л`;

  // ИСПРАВЛЕНО: Используем Layout вместо ручного добавления Navbar
  if (loading || !analytics) {
    return (
      <Layout>
        <div className="flex justify-center items-center py-20">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        </div>
      </Layout>
    );
  }

  // Подготовка данных для графика по месяцам
  const monthlyData = Object.entries(analytics.refuels_by_month).map(([month, count]) => ({
    month,
    refuels: count,
  }));

  // ИСПРАВЛЕНО: Оборачиваем всё в Layout, убираем лишний <Navbar />
  return (
    <Layout>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Заголовок */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">⛽ Учёт топлива</h1>
          <p className="text-gray-600 mt-1">
            Аналитика заправок, расхода и стоимости топлива
          </p>
        </div>

        {/* Алерты аномалий */}
        {anomalies.length > 0 && (
          <div className="mb-6">
            <h2 className="text-lg font-bold text-gray-900 mb-3">
              🚨 Обнаружено аномалий: {anomalies.length}
            </h2>
            <FuelAnomalyAlerts anomalies={anomalies} />
          </div>
        )}

        {/* Карточки с метриками */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-white rounded-lg shadow-sm p-6 border-l-4 border-blue-500">
            <div className="text-sm text-gray-600 mb-1">Общий объём</div>
            <div className="text-2xl font-bold text-gray-900">
              {formatVolume(analytics.total_volume_refuel)}
            </div>
            <div className="text-xs text-gray-500 mt-1">
              {analytics.total_refuels} заправок
            </div>
          </div>

          <div className="bg-white rounded-lg shadow-sm p-6 border-l-4 border-green-500">
            <div className="text-sm text-gray-600 mb-1">Общая стоимость</div>
            <div className="text-2xl font-bold text-gray-900">
              {formatCurrency(analytics.total_cost)}
            </div>
            <div className="text-xs text-gray-500 mt-1">
              за {analytics.period.from.split('T')[0]} — {analytics.period.to.split('T')[0]}
            </div>
          </div>

          <div className="bg-white rounded-lg shadow-sm p-6 border-l-4 border-yellow-500">
            <div className="text-sm text-gray-600 mb-1">Средняя цена</div>
            <div className="text-2xl font-bold text-gray-900">
              {analytics.avg_price_per_liter} ₽/л
            </div>
            <div className="text-xs text-gray-500 mt-1">
              за литр
            </div>
          </div>

          <div className="bg-white rounded-lg shadow-sm p-6 border-l-4 border-purple-500">
            <div className="text-sm text-gray-600 mb-1">Средний объём</div>
            <div className="text-2xl font-bold text-gray-900">
              {formatVolume(analytics.avg_volume_per_refuel)}
            </div>
            <div className="text-xs text-gray-500 mt-1">
              за заправку
            </div>
          </div>
        </div>

        {/* Графики */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {/* График заправок по месяцам */}
          <div className="bg-white rounded-lg shadow-sm p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4">📊 Заправки по месяцам</h2>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={monthlyData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="refuels" fill="#3b82f6" name="Заправки" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* График расхода по технике */}
          <div className="bg-white rounded-lg shadow-sm p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4">⛽ Расход по технике</h2>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={byVehicle} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" />
                <YAxis dataKey="vehicle_name" type="category" width={150} />
                <Tooltip />
                <Legend />
                <Bar dataKey="total_refuel_volume" fill="#10b981" name="Заправки (л)" />
                <Bar dataKey="total_drain_volume" fill="#ef4444" name="Сливы (л)" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Таблица расхода */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-8">
          <h2 className="text-lg font-bold text-gray-900 mb-4">📈 Расход топлива (л/ч и л/100км)</h2>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Техника
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Всего топлива
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Моточасы
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    л/ч
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    л/100км
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {consumption.map((item) => (
                  <tr key={item.vehicle_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm text-gray-900">{item.vehicle_name}</td>
                    <td className="px-4 py-3 text-sm text-right text-gray-900">
                      {formatVolume(item.total_fuel_liters)}
                    </td>
                    <td className="px-4 py-3 text-sm text-right text-gray-900">
                      {item.engine_hours.toFixed(1)} ч
                    </td>
                    <td className="px-4 py-3 text-sm text-right text-gray-900 font-medium">
                      {item.liters_per_hour.toFixed(2)}
                    </td>
                    <td className="px-4 py-3 text-sm text-right text-gray-900 font-medium">
                      {item.liters_per_100km?.toFixed(1) || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Таблица затрат по технике */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-lg font-bold text-gray-900 mb-4">💰 Затраты по технике</h2>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Техника
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Заправок
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Сливов
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Объём (л)
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Стоимость
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Ср. за заправку
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {byVehicle.map((item) => (
                  <tr key={item.vehicle_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm text-gray-900">{item.vehicle_name}</td>
                    <td className="px-4 py-3 text-sm text-right text-gray-900">
                      {item.refuels_count}
                    </td>
                    <td className="px-4 py-3 text-sm text-right text-gray-900">
                      {item.drains_count > 0 && (
                        <span className="text-red-600 font-medium">{item.drains_count}</span>
                      )}
                      {item.drains_count === 0 && <span className="text-gray-400">0</span>}
                    </td>
                    <td className="px-4 py-3 text-sm text-right text-gray-900">
                      {formatVolume(item.net_volume)}
                    </td>
                    <td className="px-4 py-3 text-sm text-right text-gray-900 font-medium">
                      {formatCurrency(item.total_cost)}
                    </td>
                    <td className="px-4 py-3 text-sm text-right text-gray-900">
                      {formatCurrency(item.avg_cost_per_refuel)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default FuelAnalyticsPage;