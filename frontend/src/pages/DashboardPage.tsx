import React, { useEffect, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { telematicsApi, type DashboardSummary } from '../api/telematics';

export const DashboardPage: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadDashboardData = async () => {
      try {
        setLoading(true);
        const data = await telematicsApi.getDashboardSummary();
        setSummary(data);
        setError('');
      } catch (err: any) {
        console.error('Failed to load dashboard:', err);
        setError('Не удалось загрузить данные дашборда');
      } finally {
        setLoading(false);
      }
    };

    loadDashboardData();
  }, []);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Загрузка данных...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navigation */}
      <nav className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center">
              <h1 className="text-xl font-bold text-gray-900">🚜 СпецТехника Про</h1>
            </div>
            <div className="flex items-center space-x-4">
              <span className="text-gray-700">{user?.email}</span>
              <button
                onClick={handleLogout}
                className="bg-red-600 text-white px-4 py-2 rounded hover:bg-red-700"
              >
                Выйти
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">
            Добро пожаловать, {user?.full_name || user?.email}!
          </h2>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-6">
              {error}
            </div>
          )}

          {/* Metrics Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            {/* Vehicles Card */}
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-medium text-gray-500">Техника</h3>
                <span className="text-3xl">🚜</span>
              </div>
              <div className="text-3xl font-bold text-gray-900 mb-2">
                {summary?.vehicles?.total || 0}
              </div>
              <div className="text-sm text-gray-600">
                <div className="flex justify-between">
                  <span>Активных:</span>
                  <span className="font-semibold">{summary?.vehicles?.active || 0}</span>
                </div>
              </div>
            </div>

            {/* GPS Points Card */}
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-medium text-gray-500">GPS Точки</h3>
                <span className="text-3xl">📍</span>
              </div>
              <div className="text-3xl font-bold text-gray-900 mb-2">
                {summary?.gps_points?.today || 0}
              </div>
              <div className="text-sm text-gray-600">
                <div className="flex justify-between">
                  <span>За сегодня</span>
                  <span className="text-xs text-gray-400">
                    Всего: {summary?.gps_points?.total || 0}
                  </span>
                </div>
              </div>
            </div>

            {/* Alerts Card */}
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-medium text-gray-500">Алерты</h3>
                <span className="text-3xl">⚠️</span>
              </div>
              <div className="text-3xl font-bold text-gray-900 mb-2">
                {summary?.alerts?.active || 0}
              </div>
              <div className="text-sm text-gray-600">
                <div className="flex justify-between">
                  <span>Активных</span>
                  <span className={`text-xs ${summary?.alerts?.critical ? 'text-red-600 font-semibold' : 'text-gray-400'}`}>
                    Критических: {summary?.alerts?.critical || 0}
                  </span>
                </div>
              </div>
            </div>

            {/* Fuel Card */}
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-medium text-gray-500">Топливо</h3>
                <span className="text-3xl">⛽</span>
              </div>
              <div className="text-3xl font-bold text-gray-900 mb-2">
                {summary?.fuel?.week_volume?.toFixed(0) || 0} л
              </div>
              <div className="text-sm text-gray-600">
                <div className="flex justify-between">
                  <span>За неделю</span>
                  <span className="text-xs text-gray-400">
                    {summary?.fuel?.week_cost?.toFixed(0) || 0} ₽
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Quick Actions */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Быстрые действия</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <button
                onClick={() => navigate('/vehicles')}
                className="flex items-center p-4 border-2 border-gray-200 rounded-lg hover:border-blue-500 hover:bg-blue-50 transition"
              >
                <span className="text-2xl mr-3">🚜</span>
                <div className="text-left">
                  <div className="font-medium text-gray-900">Управление техникой</div>
                  <div className="text-sm text-gray-500">Просмотр и редактирование</div>
                </div>
              </button>

              <button
                disabled
                className="flex items-center p-4 border-2 border-gray-200 rounded-lg opacity-50 cursor-not-allowed"
              >
                <span className="text-2xl mr-3">📋</span>
                <div className="text-left">
                  <div className="font-medium text-gray-900">Заявки</div>
                  <div className="text-sm text-gray-500">Скоро будет доступно</div>
                </div>
              </button>

              <button
                disabled
                className="flex items-center p-4 border-2 border-gray-200 rounded-lg opacity-50 cursor-not-allowed"
              >
                <span className="text-2xl mr-3">💰</span>
                <div className="text-left">
                  <div className="font-medium text-gray-900">Финансы</div>
                  <div className="text-sm text-gray-500">Скоро будет доступно</div>
                </div>
              </button>
            </div>
          </div>

          {/* User Info */}
          <div className="mt-8 bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Информация о пользователе</h3>
            <dl className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <dt className="text-sm text-gray-500">Email</dt>
                <dd className="text-gray-900">{user?.email}</dd>
              </div>
              <div>
                <dt className="text-sm text-gray-500">Имя</dt>
                <dd className="text-gray-900">{user?.full_name || '-'}</dd>
              </div>
              <div>
                <dt className="text-sm text-gray-500">Роль</dt>
                <dd className="text-gray-900">{user?.role || 'user'}</dd>
              </div>
              <div>
                <dt className="text-sm text-gray-500">Superuser</dt>
                <dd className="text-gray-900">{user?.is_superuser ? 'Да' : 'Нет'}</dd>
              </div>
            </dl>
          </div>
        </div>
      </main>
    </div>
  );
};

export default DashboardPage;
