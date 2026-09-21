import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { CompanySwitcher } from './CompanySwitcher';
import NotificationBell from './NotificationBell';

interface NavItem {
  path: string;
  label: string;
}

const NAV_ITEMS: NavItem[] = [
  { path: '/', label: 'Дашборд' },
  { path: '/requests', label: 'Заявки' },
  { path: '/vehicles', label: 'Техника' },
  { path: '/marketplace', label: '🎯 Маркетплейс' },  // ← ДОБАВИТЬ
  { path: '/contractors', label: 'Контрагенты' },
  { path: '/finance', label: 'Финансы' },
  { path: '/invoices', label: 'Счета' },
];

export const Navbar: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const isActive = (path: string) => {
    if (path === '/') {
      return location.pathname === '/';
    }
    return location.pathname.startsWith(path);
  };

  return (
    <nav className="bg-white shadow-sm border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          {/* Левая часть: логотип + меню + переключатель компаний */}
          <div className="flex items-center space-x-6">
            <h1
              className="text-xl font-bold text-gray-900 cursor-pointer"
              onClick={() => navigate('/')}
            >
              🚜 СпецТехника Про
            </h1>

            {/* Меню навигации */}
            <div className="hidden md:flex items-center space-x-1">
              {NAV_ITEMS.map((item) => (
                <button
                  key={item.path}
                  onClick={() => navigate(item.path)}
                  className={`px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                    isActive(item.path)
                      ? 'bg-blue-50 text-blue-700'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>

            {/* 🆕 Переключатель компаний */}
            <CompanySwitcher />
          </div>

          {/* Правая часть: уведомления, email, выход */}
          <div className="flex items-center space-x-4">
            <span className="text-sm text-gray-700 hidden sm:inline">
              {user?.email}
            </span>
            <NotificationBell />
            <button
              onClick={() => {
                logout();
                navigate('/login');
              }}
              className="bg-red-600 text-white px-4 py-2 rounded hover:bg-red-700 text-sm"
            >
              Выйти
            </button>
          </div>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
