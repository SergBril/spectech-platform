import React, { useEffect, useState } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell,
} from 'recharts';
import Layout from '../../components/Layout';
import { showToast } from '../../utils/toast';
import { adminApi, PlatformStats, ProviderRequest, ReviewsStats, FinanceStats, TopCompanies, UserActivity } from '../../api/admin';

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

const PERIOD_OPTIONS = [
  { label: '7 дней', days: 7 },
  { label: '30 дней', days: 30 },
  { label: '90 дней', days: 90 },
  { label: 'Год', days: 365 },
];

const StatCard: React.FC<{ title: string; value: number; newValue: number; icon: string }> = ({ title, value, newValue, icon }) => (
  <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
    <div className="flex items-center justify-between mb-2">
      <span className="text-2xl">{icon}</span>
      {newValue > 0 && (
        <span className="bg-green-100 text-green-700 text-xs font-medium px-2 py-0.5 rounded-full">+{newValue}</span>
      )}
    </div>
    <div className="text-3xl font-bold text-gray-900">{value}</div>
    <div className="text-sm text-gray-500 mt-1">{title}</div>
  </div>
);

const SimpleStatCard: React.FC<{ title: string; value: string | number; icon: string; subtitle?: string }> = ({ title, value, icon, subtitle }) => (
  <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
    <div className="flex items-center justify-between mb-2">
      <span className="text-2xl">{icon}</span>
    </div>
    <div className="text-3xl font-bold text-gray-900">{value}</div>
    <div className="text-sm text-gray-500 mt-1">{title}</div>
    {subtitle && <div className="text-xs text-gray-400 mt-0.5">{subtitle}</div>}
  </div>
);

export const AdminDashboardPage: React.FC = () => {
  const [stats, setStats] = useState<PlatformStats | null>(null);
  const [providerRequests, setProviderRequests] = useState<ProviderRequest[]>([]);
  const [reviewsStats, setReviewsStats] = useState<ReviewsStats | null>(null);
  const [financeStats, setFinanceStats] = useState<FinanceStats | null>(null);
  const [topCompanies, setTopCompanies] = useState<TopCompanies | null>(null);
  const [userActivity, setUserActivity] = useState<UserActivity | null>(null);
  const [loading, setLoading] = useState(true);
  const [periodDays, setPeriodDays] = useState(30);

  useEffect(() => {
    loadData();
  }, [periodDays]);

  const loadData = async () => {
    try {
      setLoading(true);
      const now = new Date();
      const from = new Date(now.getTime() - periodDays * 24 * 60 * 60 * 1000);
      const [statsData, prData, reviewsData, financeData, topCompaniesData, userActivityData] = await Promise.all([
        adminApi.getStats(from.toISOString(), now.toISOString()),
        adminApi.getProviderRequests(),
        adminApi.getReviewsStats(),
        adminApi.getFinanceStats(from.toISOString(), now.toISOString()),
        adminApi.getTopCompanies(10),
        adminApi.getUserActivity(),
      ]);
      setStats(statsData);
      setProviderRequests(prData.requests);
      setReviewsStats(reviewsData);
      setFinanceStats(financeData);
      setTopCompanies(topCompaniesData);
      setUserActivity(userActivityData);
    } catch (err: any) {
      if (err?.response?.status === 403) {
        showToast.error('Доступ запрещён. Требуются права администратора.');
      } else {
        showToast.error('Ошибка загрузки статистики: ' + (err as Error).message);
      }
    } finally {
      setLoading(false);
    }
  };

  const vehicleStatusData = stats
    ? Object.entries(stats.vehicles_by_status).map(([name, value]) => ({ name, value }))
    : [];

  const requestStatusData = stats
    ? Object.entries(stats.requests_by_status).map(([name, value]) => ({ name, value }))
    : [];

  const barData = stats
    ? [
        { name: 'Пользователи', total: stats.totals.users, new: stats.new_in_period.users },
        { name: 'Компании', total: stats.totals.companies, new: stats.new_in_period.companies },
        { name: 'Техника', total: stats.totals.vehicles, new: stats.new_in_period.vehicles },
        { name: 'Заявки', total: stats.totals.requests, new: stats.new_in_period.requests },
      ]
    : [];

  const ratingData = reviewsStats
    ? [
        { name: 'Общий', value: reviewsStats.avg_rating },
        { name: 'Качество', value: reviewsStats.avg_quality },
        { name: 'Пунктуальность', value: reviewsStats.avg_punctuality },
        { name: 'Коммуникация', value: reviewsStats.avg_communication },
      ]
    : [];

  return (
    <Layout>
      <div className="px-6 py-6 max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-6 gap-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">📊 Админ-панель платформы</h1>
            <p className="text-sm text-gray-500 mt-1">Обзор метрик и заявок пользователей</p>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600">Период:</span>
            <select
              value={periodDays}
              onChange={(e) => setPeriodDays(Number(e.target.value))}
              className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
            >
              {PERIOD_OPTIONS.map((opt) => (
                <option key={opt.days} value={opt.days}>{opt.label}</option>
              ))}
            </select>
          </div>
        </div>

        {loading ? (
          <div className="flex justify-center py-20">
            <div className="w-10 h-10 border-4 border-blue-200 rounded-full animate-spin border-t-blue-600" />
          </div>
        ) : !stats ? (
          <div className="text-center py-20 text-gray-500">Нет данных или недостаточно прав</div>
        ) : (
          <div className="space-y-6">
            {/* Stat Cards */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard title="Пользователей" value={stats.totals.users} newValue={stats.new_in_period.users} icon="👥" />
              <StatCard title="Компаний" value={stats.totals.companies} newValue={stats.new_in_period.companies} icon="🏢" />
              <StatCard title="Техники" value={stats.totals.vehicles} newValue={stats.new_in_period.vehicles} icon="🚜" />
              <StatCard title="Заявок" value={stats.totals.requests} newValue={stats.new_in_period.requests} icon="📋" />
            </div>

            {/* Finance Section */}
            {financeStats && (
              <div className="bg-gradient-to-r from-green-50 to-emerald-50 rounded-xl p-5 border border-green-200">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">💰 Финансовая сводка</h3>
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  <SimpleStatCard title="Счетов" value={financeStats.total_invoices} icon="📄" />
                  <SimpleStatCard title="Выручка" value={`${financeStats.total_revenue.toLocaleString('ru-RU')} ₽`} icon="💵" />
                  <SimpleStatCard title="Не оплачено" value={`${financeStats.unpaid_amount.toLocaleString('ru-RU')} ₽`} icon="⏳" />
                  <SimpleStatCard title="Платежей" value={financeStats.total_payments} icon="💳" />
                </div>
              </div>
            )}

            {/* Reviews Section */}
            {reviewsStats && (
              <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">⭐ Отзывы и рейтинги</h3>
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
                  <SimpleStatCard title="Всего отзывов" value={reviewsStats.total_reviews} icon="💬" />
                  <SimpleStatCard title="Одобрено" value={reviewsStats.approved_reviews} icon="✅" />
                  <SimpleStatCard title="На модерации" value={reviewsStats.pending_reviews} icon="⏳" />
                  <SimpleStatCard title="Средний рейтинг" value={`${reviewsStats.avg_rating}/5`} icon="⭐" />
                </div>
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={ratingData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                    <YAxis domain={[0, 5]} tick={{ fontSize: 12 }} />
                    <Tooltip />
                    <Bar dataKey="value" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* User Activity */}
            {userActivity && (
              <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl p-5 border border-blue-200">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">👥 Активность пользователей</h3>
                <div className="grid grid-cols-2 gap-4">
                  <SimpleStatCard title="Новых сегодня" value={userActivity.new_today} icon="🆕" />
                  <SimpleStatCard title="Новых за неделю" value={userActivity.new_this_week} icon="📈" />
                </div>
              </div>
            )}

            {/* Charts Row */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Bar Chart */}
              <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">📈 Рост за период</h3>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={barData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                    <YAxis tick={{ fontSize: 12 }} />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="total" name="Всего" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="new" name="Новых" fill="#10b981" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* Pie Charts */}
              <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">🚜 Техника по статусам</h3>
                {vehicleStatusData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={300}>
                    <PieChart>
                      <Pie data={vehicleStatusData} cx="50%" cy="50%" outerRadius={100} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>
                        {vehicleStatusData.map((_, i) => (
                          <Cell key={i} fill={COLORS[i % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex items-center justify-center h-[300px] text-gray-400">Нет данных</div>
                )}
              </div>
            </div>

            {/* Top Companies */}
            {topCompanies && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">🏆 Топ компаний по заявкам</h3>
                  <div className="space-y-2">
                    {topCompanies.top_by_requests.map((company, i) => (
                      <div key={company.id} className="flex items-center justify-between p-2 hover:bg-gray-50 rounded">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-gray-500">#{i + 1}</span>
                          <span className="text-sm font-medium text-gray-900">{company.name}</span>
                        </div>
                        <span className="text-sm text-blue-600 font-semibold">{company.count}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">🚜 Топ компаний по технике</h3>
                  <div className="space-y-2">
                    {topCompanies.top_by_vehicles.map((company, i) => (
                      <div key={company.id} className="flex items-center justify-between p-2 hover:bg-gray-50 rounded">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-gray-500">#{i + 1}</span>
                          <span className="text-sm font-medium text-gray-900">{company.name}</span>
                        </div>
                        <span className="text-sm text-green-600 font-semibold">{company.count}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Requests Status Chart */}
            <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">📋 Заявки по статусам</h3>
              {requestStatusData.length > 0 ? (
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={requestStatusData} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" tick={{ fontSize: 12 }} />
                    <YAxis dataKey="name" type="category" width={120} tick={{ fontSize: 12 }} />
                    <Tooltip />
                    <Bar dataKey="value" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-[250px] text-gray-400">Нет данных</div>
              )}
            </div>

            {/* Provider Requests */}
            <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">📨 Запросы новых GPS-провайдеров</h3>
              {providerRequests.length === 0 ? (
                <div className="text-center py-8 text-gray-400">Нет запросов</div>
              ) : (
                <div className="divide-y">
                  {providerRequests.map((req) => (
                    <div key={req.id} className={`py-3 ${req.is_read ? 'opacity-60' : ''}`}>
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="font-medium text-gray-900">{req.title}</div>
                          <div className="text-sm text-gray-600 mt-1 whitespace-pre-line">{req.body}</div>
                        </div>
                        <div className="text-xs text-gray-400 whitespace-nowrap ml-4">
                          {req.sent_at ? new Date(req.sent_at).toLocaleString('ru-RU') : '—'}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default AdminDashboardPage;
