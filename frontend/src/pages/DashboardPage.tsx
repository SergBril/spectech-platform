import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { vehiclesApi, type Vehicle } from '../api/vehicles';
import { requestsApi, type Request } from '../api/requests';
import { financeApi, type PaymentsDashboard } from '../api/finance';
import apiClient from '../api/client';
import { lazy, Suspense } from 'react';
const RevenueChart = lazy(() => import('../components/AnalyticsCharts').then(m => ({ default: m.RevenueChart })));
const StatusPieChart = lazy(() => import('../components/AnalyticsCharts').then(m => ({ default: m.StatusPieChart })));
const TopRequestsChart = lazy(() => import('../components/AnalyticsCharts').then(m => ({ default: m.TopRequestsChart })));
const Sparkline = lazy(() => import('../components/AnalyticsCharts').then(m => ({ default: m.Sparkline })));
import { MetricCardSkeleton, ChartSkeleton } from '../components/Skeleton';
import DispatcherDashboard from '../components/DispatcherDashboard';
import Layout from '../components/Layout';
import DashboardWidgets from '../components/DashboardWidgets';
import EmptyState from '../components/EmptyState';

export const DashboardPage: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [requests, setRequests] = useState<Request[]>([]);
  const [financeData, setFinanceData] = useState<PaymentsDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const [gpsStats, setGpsStats] = useState<{ total_points: number; vehicles_with_data: number; latest_point: string | null } | null>(null);
  const [usersCount, setUsersCount] = useState<number>(0);
  const [driversCount, setDriversCount] = useState<number>(0);
  const [mpStats, setMpStats] = useState<any>(null);
  const [platformOverview, setPlatformOverview] = useState<any>(null);
  const [period, setPeriod] = useState<{ from: string; to: string }>({ from: '', to: '' });

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
      if (financeRes.status === 'fulfilled') {
        const fd = financeRes.value as any;
        // Map API response to frontend expected format
        const mapped: any = {
          ...fd,
          total_revenue: fd.revenue?.total ?? fd.total_revenue ?? 0,
          total_paid: fd.revenue?.paid ?? fd.total_paid ?? 0,
          outstanding: fd.revenue?.outstanding ?? fd.outstanding ?? 0,
          invoices_count: fd.metrics?.invoices_count ?? fd.invoices_count ?? 0,
          acts_count: fd.metrics?.acts_count ?? fd.acts_count ?? 0,
        };
        setFinanceData(mapped);
      }

      // Load GPS stats
      try {
        const gpsRes = await apiClient.get('/gps/points/stats');
        setGpsStats(gpsRes.data);
      } catch { /* ignore */ }

      // Load users count via drivers/users endpoint
      try {
        const usersRes = await apiClient.get('/drivers/users');
        setUsersCount(Array.isArray(usersRes.data) ? usersRes.data.length : 0);
      } catch { /* ignore */ }

      // Load drivers count from /drivers endpoint
      try {
        const driversRes = await apiClient.get('/drivers', { params: { limit: 1 } });
        setDriversCount(driversRes.data?.total ?? (Array.isArray(driversRes.data) ? driversRes.data.length : 0));
      } catch { /* ignore */ }

      // Load marketplace stats
      try {
        const mpRes = await apiClient.get('/public/marketplace/stats');
        setMpStats(mpRes.data);
      } catch { /* ignore */ }

      // Load platform overview (idle/busy vehicles, acts, transactions)
      try {
        const poRes = await apiClient.get('/shifts/stats/platform-overview');
        setPlatformOverview(poRes.data);
      } catch { /* ignore */ }
    } catch (err) {
      console.error('Failed to load dashboard:', err);
    } finally {
      setLoading(false);
      setIsInitialLoading(false);
    }
  };

  const activeVehicles = vehicles.filter(
    (v) => v.status === 'free' || (v.status as string) === 'working'
  ).length;
  const pendingRequests = requests.filter(
    (r) => r.status === 'new' || r.status === 'processing'
  ).length;

  if (isInitialLoading && loading) {
    return (
      <Layout>
      <div className="mb-6"><DispatcherDashboard /></div>
        <div className="space-y-8">
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
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="space-y-8">
        {/* === ПРИВЕТСТВИЕ === */}
        <div className="bg-gradient-to-r from-blue-500 to-indigo-600 rounded-lg shadow-lg p-6 text-white">
          <h2 className="text-2xl font-bold mb-2">
            Добро пожаловать, {user?.email?.split('@')[0]}!
          </h2>
          <p className="text-blue-100">Обзор вашей спецтехники и финансов на сегодня</p>
          <div className="flex items-center gap-3 mt-4">
            <label className="text-sm text-blue-100">Период:</label>
            <input type="date" value={period.from} onChange={(e) => setPeriod(p => ({ ...p, from: e.target.value }))}
              className="px-2 py-1 rounded text-gray-900 text-sm" />
            <span className="text-blue-100">—</span>
            <input type="date" value={period.to} onChange={(e) => setPeriod(p => ({ ...p, to: e.target.value }))}
              className="px-2 py-1 rounded text-gray-900 text-sm" />
            {(period.from || period.to) && (
              <button onClick={() => setPeriod({ from: '', to: '' })}
                className="px-3 py-1 bg-white/20 hover:bg-white/30 rounded text-sm text-white transition-colors">
                Сбросить
              </button>
            )}
          </div>
        </div>

        {/* === КЛЮЧЕВЫЕ МЕТРИКИ === */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
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
                  {financeData
                    ? `${parseFloat(financeData.total_revenue).toLocaleString('ru-RU')} ₽`
                    : '—'}
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
                  {financeData
                    ? `${parseFloat(financeData.total_paid).toLocaleString('ru-RU')} ₽`
                    : '—'}
                </p>
                <p className="text-xs text-gray-600">Актов: {financeData?.acts_count || 0}</p>
              </div>
              <span className="text-4xl">✅</span>
            </div>
          </div>
        </div>

        {/* === СВОДКА ПО ТЕХНИКЕ (Platform Overview) === */}
        {platformOverview && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500">Смен сегодня</p>
                  <p className="text-3xl font-bold text-indigo-600">{platformOverview.shifts_today ?? 0}</p>
                </div>
                <span className="text-4xl">📅</span>
              </div>
            </div>
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500">Актов за месяц</p>
                  <p className="text-3xl font-bold text-green-600">{platformOverview.acts_this_month?.count ?? 0}</p>
                  <p className="text-xs text-gray-600">
                    Выручка: {(platformOverview.acts_this_month?.revenue ?? 0).toLocaleString('ru-RU')} ₽
                  </p>
                </div>
                <span className="text-4xl">📄</span>
              </div>
            </div>
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500">Просроченные акты</p>
                  <p className={`text-3xl font-bold ${platformOverview.overdue_acts > 0 ? 'text-red-600' : 'text-gray-900'}`}>
                    {platformOverview.overdue_acts ?? 0}
                  </p>
                </div>
                <span className="text-4xl">⚠️</span>
              </div>
            </div>
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500">Транзакции за месяц</p>
                  <p className="text-3xl font-bold text-blue-600">{platformOverview.transactions_this_month?.count ?? 0}</p>
                  <p className="text-xs text-gray-600">
                    Неразнесено: {platformOverview.unmatched_transactions ?? 0}
                  </p>
                </div>
                <span className="text-4xl">🏦</span>
              </div>
            </div>
          </div>
        )}

        {/* === ПОЛЬЗОВАТЕЛИ И ВОДИТЕЛИ === */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Пользователи системы</p>
                <p className="text-3xl font-bold text-gray-900">{usersCount}</p>
              </div>
              <span className="text-4xl">👤</span>
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Водители</p>
                <p className="text-3xl font-bold text-gray-900">{driversCount}</p>
              </div>
              <span className="text-4xl">👷</span>
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Техника на карте</p>
                <p className="text-3xl font-bold text-indigo-600">{gpsStats?.vehicles_with_data ?? 0}</p>
                <p className="text-xs text-gray-600">С GPS-данными</p>
              </div>
              <span className="text-4xl">🗺️</span>
            </div>
          </div>
        </div>

        {/* === ВИДЖЕТЫ === */}
        {!isInitialLoading && <DashboardWidgets />}

        {/* === ГРАФИКИ === */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <RevenueChart dateFrom={period.from || undefined} dateTo={period.to || undefined} />
          <StatusPieChart dateFrom={period.from || undefined} dateTo={period.to || undefined} />
        </div>

        {/* === ТОП ЗАЯВОК + SPARKLINE === */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <TopRequestsChart dateFrom={period.from || undefined} dateTo={period.to || undefined} />
          </div>
          <div className="space-y-6">
            <Sparkline />
            <div className="bg-white rounded-lg shadow p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-gray-500 uppercase font-semibold">GPS точки</p>
                  <p className="text-xl font-bold text-gray-900">{gpsStats?.total_points?.toLocaleString('ru-RU') ?? '—'}</p>
                  <p className="text-xs text-gray-600">{gpsStats?.vehicles_with_data ? `${gpsStats.vehicles_with_data} ед. с данными` : 'Всего'}</p>
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

            {/* Маркетплейс */}
            <div className="bg-white rounded-xl shadow-sm border p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900">🌐 Маркетплейс</h3>
                <a href="/marketplace" className="text-sm text-blue-600 hover:underline">Перейти →</a>
              </div>
              {mpStats ? (
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-3 bg-purple-50 rounded-lg">
                    <p className="text-xs text-gray-500">Активных заявок</p>
                    <p className="text-2xl font-bold text-purple-700">{mpStats.active_requests}</p>
                  </div>
                  <div className="p-3 bg-green-50 rounded-lg">
                    <p className="text-xs text-gray-500">Назначено</p>
                    <p className="text-2xl font-bold text-green-700">{mpStats.assigned_requests}</p>
                  </div>
                  <div className="p-3 bg-orange-50 rounded-lg">
                    <p className="text-xs text-gray-500">Ожидает одобрения</p>
                    <p className="text-2xl font-bold text-orange-700">{mpStats.pending_responses}</p>
                  </div>
                  <div className="p-3 bg-blue-50 rounded-lg">
                    <p className="text-xs text-gray-500">Ср. срок оплаты</p>
                    <p className="text-2xl font-bold text-blue-700">{mpStats.avg_payment_days} дн.</p>
                  </div>
                  <div className="col-span-2 flex gap-2 mt-2">
                    <span className="px-2 py-1 bg-purple-100 text-purple-800 rounded text-xs font-medium">
                      🏪 Заказчики: {mpStats.client_requests}
                    </span>
                    <span className="px-2 py-1 bg-orange-100 text-orange-800 rounded text-xs font-medium">
                      📋 Диспетчеры: {mpStats.dispatcher_requests}
                    </span>
                  </div>
                </div>
              ) : (
                <div className="text-center py-8 text-gray-400 text-sm">Загрузка...</div>
              )}
            </div>
          </div>
        </div>

        {/* === БЫСТРЫЕ ДЕЙСТВИЯ === */}
        <div>
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Быстрые действия</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <button
              onClick={() => navigate('/vehicles')}
              className="bg-white rounded-lg shadow p-6 hover:shadow-lg transition-shadow text-left"
            >
              <span className="text-4xl">🚜</span>
              <h4 className="mt-3 text-lg font-semibold text-gray-900">Управление техникой</h4>
              <p className="text-sm text-gray-600">Просмотр и редактирование</p>
            </button>
            <button
              onClick={() => navigate('/requests')}
              className="bg-white rounded-lg shadow p-6 hover:shadow-lg transition-shadow text-left"
            >
              <span className="text-4xl">📋</span>
              <h4 className="mt-3 text-lg font-semibold text-gray-900">Заявки</h4>
              <p className="text-sm text-gray-600">Управление заявками</p>
            </button>
            <button
              onClick={() => navigate('/finance')}
              className="bg-white rounded-lg shadow p-6 hover:shadow-lg transition-shadow text-left"
            >
              <span className="text-4xl">💰</span>
              <h4 className="mt-3 text-lg font-semibold text-gray-900">Финансы</h4>
              <p className="text-sm text-gray-600">Счета, акты, выплаты</p>
            </button>
            <button
              onClick={() => navigate('/contractors')}
              className="bg-white rounded-lg shadow p-6 hover:shadow-lg transition-shadow text-left"
            >
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
              <dd className="font-medium text-gray-900">{(user as any)?.role || (user as any)?.is_superuser ? 'Администратор' : 'Пользователь'}</dd>
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