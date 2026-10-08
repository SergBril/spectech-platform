import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { vehiclesApi, type Vehicle } from '../api/vehicles';
import { requestsApi, type Request } from '../api/requests';
import { financeApi, type PaymentsDashboard } from '../api/finance';
import { RevenueChart, StatusPieChart, TopRequestsChart, Sparkline } from '../components/AnalyticsCharts';
import { MetricCardSkeleton, ChartSkeleton } from '../components/Skeleton';
import NotificationBell from '../components/NotificationBell';
import Layout from '../components/Layout';
import DashboardWidgets from '../components/DashboardWidgets';

export const DashboardPage: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [requests, setRequests] = useState<Request[]>([]);
  const [financeData, setFinanceData] = useState<PaymentsDashboard | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [vehiclesData, requestsData, financeRes] = await Promise.allSettled([
        vehiclesApi.getAll({ limit: 100 }),
        requestsApi.getAll({ limit: 100 }),
        financeApi.getDashboard(),
      ]);

      if (vehiclesData.status === 'fulfilled') setVehicles(vehiclesData.value);
      if (requestsData.status === 'fulfilled') setRequests(requestsData.value);
      if (financeRes.status === 'fulfilled') setFinanceData(financeRes.value);
    } catch (err) {
      console.error('Failed to load dashboard:', err);
    } finally {
      setLoading(false);
    }
  };

  const activeVehicles = vehicles.filter((v) => v.status === 'free' || (v.status as string) === 'working').length;
  const pendingRequests = requests.filter((r) => r.status === 'new' || r.status === 'processing').length;

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Layout />

        <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
          <div className="bg-gradient-to-r from-blue-500 to-indigo-600 rounded-lg shadow-lg p-6 animate-pulse">
            <div className="w-64 h-8 bg-blue-400 rounded mb-2 opacity-50" />
            <div className="w-96 h-5 bg-blue-400 rounded opacity-50" />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <MetricCardSkeleton />
            <MetricCardSkeleton />
            <MetricCardSkeleton />
            <MetricCardSkeleton />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <ChartSkeleton />
            <ChartSkeleton />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2">
              <ChartSkeleton height={250} />
            </div>
            <div className="space-y-6">
              <ChartSkeleton height={100} />
              <ChartSkeleton height={80} />
              <ChartSkeleton height={80} />
            </div>
          </div>
        </main>
      </div>
    );
  }

  return (
    <Layout>
      <div className="space-y-8">
        {/* === ПРИВЕТСТВИЕ === */}
        <div className="bg-gradient-to-r from-blue-500 to-indigo-600 rounded-lg shadow-lg p-6 text-white">
          <h2 className="text-2xl font-bold mb-2">Добро пожаловать, {user?.email?.split('@')[0]}!</h2>
          <p className="text-blue-100">Обзор вашей спецтехники и финансов на сегодня</p>
        </div>

        {/* === КЛЮЧЕВЫЕ МЕТРИКИ === */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {/* ... все ваши метрики без изменений ... */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Техника</p>
                <p className="text-3xl font-bold text-gray-900">{vehicles.length}</p>
                <p className="text-xs text-green-600">Активных: {activeVehicles}</p>
              </div>
              <span className="text-4xl">🚜</span>
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Заявки</p>
                <p className="text-3xl font-bold text-gray-900">{requests.length}</p>
                <p className="text-xs text-orange-600">В обработке: {pendingRequests}</p>
              </div>
              <span className="text-4xl">📋</span>
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Общий доход</p>
                <p className="text-2xl font-bold text-green-600">
                  {financeData ? `${parseFloat(financeData.total_revenue).toLocaleString('ru-RU')} ₽` : '—'}
                </p>
                <p className="text-xs text-gray-600">Счетов: {financeData?.invoices_count || 0}</p>
              </div>
              <span className="text-4xl">💰</span>
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Оплачено</p>
                <p className="text-2xl font-bold text-blue-600">
                  {financeData ? `${parseFloat(financeData.total_paid).toLocaleString('ru-RU')} ₽` : '—'}
                </p>
                <p className="text-xs text-gray-600">Актов: {financeData?.acts_count || 0}</p>
              </div>
              <span className="text-4xl">✅</span>
            </div>
          </div>
        </div>

        {/* === ФИНАНСОВО-ОПЕРАЦИОННЫЕ ВИДЖЕТЫ === */}
        <DashboardWidgets />

        {/* === ГРАФИКИ АНАЛИТИКИ === */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <RevenueChart />
          <StatusPieChart />
        </div>

        {/* === ТОП ЗАЯВОК + SPARKLINE === */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <TopRequestsChart />
          </div>
          <div className="space-y-6">
            <Sparkline />
            <div className="bg-white rounded-lg shadow p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-gray-500 uppercase font-semibold">GPS точки</p>
                  <p className="text-xl font-bold text-gray-900">0</p>
                  <p className="text-xs text-gray-600">Всего</p>
                </div>
                <span className="text-3xl">📍</span>
              </div>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-gray-500 uppercase font-semibold">Алерты</p>
                  <p className="text-xl font-bold text-orange-600">0</p>
                  <p className="text-xs text-gray-600">Активных</p>
                </div>
                <span className="text-3xl">⚠️</span>
              </div>
            </div>
          </div>
        </div>

        {/* === БЫСТРЫЕ ДЕЙСТВИЯ === */}
        <div>
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Быстрые действия</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <button onClick={() => navigate('/vehicles')} className="bg-white rounded-lg shadow p-6 hover:shadow-lg transition-shadow text-left">
              <span className="text-4xl">🚜</span>
              <h4 className="mt-3 text-lg font-semibold text-gray-900">Управление техникой</h4>
              <p className="text-sm text-gray-600">Просмотр и редактирование</p>
            </button>
            <button onClick={() => navigate('/requests')} className="bg-white rounded-lg shadow p-6 hover:shadow-lg transition-shadow text-left">
              <span className="text-4xl">📋</span>
              <h4 className="mt-3 text-lg font-semibold text-gray-900">Заявки</h4>
              <p className="text-sm text-gray-600">Управление заявками</p>
            </button>
            <button onClick={() => navigate('/finance')} className="bg-white rounded-lg shadow p-6 hover:shadow-lg transition-shadow text-left">
              <span className="text-4xl">💰</span>
              <h4 className="mt-3 text-lg font-semibold text-gray-900">Финансы</h4>
              <p className="text-sm text-gray-600">Счета, акты, выплаты</p>
            </button>
            <button onClick={() => navigate('/contractors')} className="bg-white rounded-lg shadow p-6 hover:shadow-lg transition-shadow text-left">
              <span className="text-4xl">👥</span>
              <h4 className="mt-3 text-lg font-semibold text-gray-900">Контрагенты</h4>
              <p className="text-sm text-gray-600">Клиенты и партнёры</p>
            </button>
          </div>
        </div>

        {/* === ИНФО О ПОЛЬЗОВАТЕЛЕ === */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Информация о пользователе</h3>
          <dl className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
            <div>
              <dt className="text-gray-500">Email</dt>
              <dd className="font-medium text-gray-900">{user?.email}</dd>
            </div>
            <div>
              <dt className="text-gray-500">Роль</dt>
              <dd className="font-medium text-gray-900">user</dd>
            </div>
            <div>
              <dt className="text-gray-500">Superuser</dt>
              <dd className="font-medium text-gray-900">Да</dd>
            </div>
          </dl>
        </div>
      </div>
    </Layout>
  );
};

export default DashboardPage;
