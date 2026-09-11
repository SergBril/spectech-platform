import React from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';

export const DashboardPage: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-gray-50">
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

      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">
            Добро пожаловать, {user?.full_name || user?.email}!
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <button
              onClick={() => navigate('/vehicles')}
              className="bg-white shadow rounded-lg p-6 hover:shadow-lg transition text-left"
            >
              <div className="text-3xl mb-2">🚜</div>
              <h3 className="text-lg font-medium text-gray-900 mb-1">Спецтехника</h3>
              <p className="text-gray-600 text-sm">Управление парком техники</p>
            </button>

            <div className="bg-white shadow rounded-lg p-6 opacity-50">
              <div className="text-3xl mb-2">📋</div>
              <h3 className="text-lg font-medium text-gray-900 mb-1">Заявки</h3>
              <p className="text-gray-600 text-sm">Скоро будет доступно</p>
            </div>

            <div className="bg-white shadow rounded-lg p-6 opacity-50">
              <div className="text-3xl mb-2">💰</div>
              <h3 className="text-lg font-medium text-gray-900 mb-1">Финансы</h3>
              <p className="text-gray-600 text-sm">Скоро будет доступно</p>
            </div>
          </div>

          <div className="mt-8 bg-white shadow rounded-lg p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">
              Информация о пользователе
            </h3>
            <dl className="grid grid-cols-2 gap-4">
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
