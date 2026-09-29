import React, { useEffect, useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { financeApi, type ClientRevenue, type VehicleRevenue } from '../api/finance';

interface Props {
  dateFrom: string;
  dateTo: string;
}

const formatMoney = (value: number) => {
  if (value >= 1000000) return `${(value / 1000000).toFixed(1)}М`;
  if (value >= 1000) return `${(value / 1000).toFixed(0)}К`;
  return value.toFixed(0);
};

export const FinancialCharts: React.FC<Props> = ({ dateFrom, dateTo }) => {
  const [clients, setClients] = useState<ClientRevenue[]>([]);
  const [vehicles, setVehicles] = useState<VehicleRevenue[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, [dateFrom, dateTo]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [clientsData, vehiclesData] = await Promise.allSettled([
        financeApi.getRevenueByClient(dateFrom, dateTo, 5),
        financeApi.getRevenueByVehicle(dateFrom, dateTo, 5),
      ]);

      if (clientsData.status === 'fulfilled') setClients(clientsData.value);
      if (vehiclesData.status === 'fulfilled') setVehicles(vehiclesData.value);
    } catch (err) {
      console.error('Failed to load charts:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <div className="bg-white rounded-lg shadow p-6 h-80 animate-pulse">
          <div className="w-48 h-6 bg-gray-200 rounded mb-4" />
          <div className="h-56 bg-gray-100 rounded" />
        </div>
        <div className="bg-white rounded-lg shadow p-6 h-80 animate-pulse">
          <div className="w-48 h-6 bg-gray-200 rounded mb-4" />
          <div className="h-56 bg-gray-100 rounded" />
        </div>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
      {/* Top клиентов по выручке */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          🏆 Топ-5 клиентов по выручке
        </h3>
        {clients.length === 0 ? (
          <div className="flex items-center justify-center h-56 text-gray-500">
            Нет данных за период
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={clients} layout="vertical" margin={{ left: 20, right: 20 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tickFormatter={formatMoney} />
              <YAxis
                type="category"
                dataKey="client_name"
                width={120}
                tick={{ fontSize: 11 }}
              />
              <Tooltip
                formatter={(value: number) => [
                  `${value.toLocaleString('ru-RU', { minimumFractionDigits: 2 })} ₽`,
                  'Выручка',
                ]}
              />
              <Bar
                dataKey="total_revenue"
                fill="#3B82F6"
                radius={[0, 4, 4, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Top техники по моточасам */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          🚜 Топ-5 техники по моточасам
        </h3>
        {vehicles.length === 0 ? (
          <div className="flex items-center justify-center h-56 text-gray-500">
            Нет данных за период
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={vehicles} layout="vertical" margin={{ left: 20, right: 20 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" />
              <YAxis
                type="category"
                dataKey="vehicle_name"
                width={140}
                tick={{ fontSize: 11 }}
              />
              <Tooltip
                formatter={(value: number, name: string) => {
                  if (name === 'moto_hours') return [`${value.toFixed(2)} м/ч`, 'Моточасы'];
                  return [value, name];
                }}
              />
              <Bar
                dataKey="moto_hours"
                fill="#10B981"
                radius={[0, 4, 4, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
};

export default FinancialCharts;
