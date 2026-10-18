import React, { useEffect, useState } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  PieChart, Pie, Cell,
  BarChart, Bar,
} from 'recharts';
import {
  analyticsApi,
  type RevenueChartData,
  type StatusChartData,
  type TopRequestData,
  type SparklineData,
} from '../api/analytics';

const formatMoney = (value: number) => {
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
};

interface DateFilterProps {
  dateFrom?: string;
  dateTo?: string;
}

export const RevenueChart: React.FC<DateFilterProps> = ({ dateFrom, dateTo }) => {
  const [data, setData] = useState<RevenueChartData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    analyticsApi.getRevenueChart(12, dateFrom, dateTo)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [dateFrom, dateTo]);

  if (loading) return <div className="h-64 flex items-center justify-center text-gray-500">Загрузка...</div>;
  if (data.length === 0) return <div className="h-64 flex items-center justify-center text-gray-500">Нет данных</div>;

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">📈 Доходы по месяцам</h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="month" />
          <YAxis tickFormatter={(value) => `${(value / 1000).toFixed(0)}k`} />
          <Tooltip formatter={(value: any) => formatMoney(value)} />
          <Legend />
          <Line type="monotone" dataKey="total" stroke="#3B82F6" name="Всего" strokeWidth={2} />
          <Line type="monotone" dataKey="paid" stroke="#10B981" name="Оплачено" strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export const StatusPieChart: React.FC<DateFilterProps> = ({ dateFrom, dateTo }) => {
  const [data, setData] = useState<StatusChartData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    analyticsApi.getStatusChart(dateFrom, dateTo)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [dateFrom, dateTo]);

  if (loading) return <div className="h-64 flex items-center justify-center text-gray-500">Загрузка...</div>;
  if (data.length === 0) return <div className="h-64 flex items-center justify-center text-gray-500">Нет данных</div>;

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">🥧 Статусы счетов</h3>
      <ResponsiveContainer width="100%" height={300}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            labelLine={false}
            label={(entry) => `${entry.name}: ${entry.value}`}
            outerRadius={80}
            fill="#8884d8"
            dataKey="value"
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
};

export const TopRequestsChart: React.FC<DateFilterProps> = ({ dateFrom, dateTo }) => {
  const [data, setData] = useState<TopRequestData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    analyticsApi.getTopRequests(5, dateFrom, dateTo)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [dateFrom, dateTo]);

  if (loading) return <div className="h-64 flex items-center justify-center text-gray-500">Загрузка...</div>;
  if (data.length === 0) return <div className="h-64 flex items-center justify-center text-gray-500">Нет данных</div>;

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">🏆 Топ-5 заявок</h3>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data} layout="vertical">
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis type="number" tickFormatter={(value) => `${(value / 1000).toFixed(0)}k`} />
          <YAxis type="category" dataKey="work_type" width={150} />
          <Tooltip formatter={(value: any) => formatMoney(value)} />
          <Bar dataKey="amount" fill="#8B5CF6" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

export const Sparkline: React.FC = () => {
  const [data, setData] = useState<SparklineData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    analyticsApi.getSparkline(7)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="h-16 flex items-center justify-center text-gray-500">Загрузка...</div>;
  if (data.length === 0) return <div className="h-16 flex items-center justify-center text-gray-500">Нет данных</div>;

  const total = data.reduce((sum, d) => sum + d.total, 0);

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-sm font-medium text-gray-600">📊 Тренд за 7 дней</h4>
        <span className="text-lg font-bold text-gray-900">{formatMoney(total)}</span>
      </div>
      <ResponsiveContainer width="100%" height={60}>
        <LineChart data={data}>
          <Line type="monotone" dataKey="total" stroke="#10B981" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};
