import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

interface MenuItem {
  label: string;
  icon: string;
  path: string;
  group?: string;
}

const menuItems: MenuItem[] = [
  { label: 'Дашборд', icon: '🏠', path: '/', group: 'Основное' },
  { label: 'Заявки', icon: '📋', path: '/requests', group: 'Основное' },
  { label: 'Техника', icon: '🚜', path: '/vehicles', group: 'Основное' },
  { label: 'Карта', icon: '🗺️', path: '/map', group: 'Телематика' },

  { label: 'Маркетплейс', icon: '🎯', path: '/marketplace', group: 'Бизнес' },
  { label: 'Мои публикации', icon: '🏪', path: '/my-listings', group: 'Бизнес' },
  { label: 'Контрагенты', icon: '👥', path: '/contractors', group: 'Бизнес' },

  { label: 'Топливо', icon: '⛽', path: '/fuel/analytics', group: 'Эксплуатация' },
  { label: 'ТО и Ремонты', icon: '🔧', path: '/maintenance', group: 'Эксплуатация' },
  { label: 'Сверки', icon: '📊', path: '/reconciliation', group: 'Эксплуатация' },

  { label: 'Финансы', icon: '💰', path: '/finance', group: 'Финансы' },
  { label: 'Счета', icon: '📄', path: '/invoices', group: 'Финансы' },
  { label: 'Банковские выписки', icon: '🏦', path: '/bank-statements', group: 'Финансы' },
  { label: 'Зарплаты', icon: '💰', path: '/salaries', group: 'Финансы' },

  { label: 'Email шаблоны', icon: '📧', path: '/email-templates', group: 'Система' },
  { label: 'Email логи', icon: '📨', path: '/email-logs', group: 'Система' },
  { label: 'Настройки', icon: '⚙️', path: '/settings/company', group: 'Система' },
  { label: 'Админ-панель', icon: '📊', path: '/admin/dashboard', group: 'Система' },
];

export const Sidebar: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  const [hoveredItem, setHoveredItem] = useState<string | null>(null);

  const isActive = (path: string) => {
    if (path === '/') return location.pathname === '/';
    return location.pathname.startsWith(path);
  };

  // Группируем пункты меню
  const groups = menuItems.reduce((acc, item) => {
    const group = item.group || 'Другое';
    if (!acc[group]) acc[group] = [];
    acc[group].push(item);
    return acc;
  }, {} as Record<string, MenuItem[]>);

  return (
    <aside
      className={`h-full bg-gradient-to-b from-gray-900 to-gray-950 text-white flex flex-col transition-all duration-300 ease-in-out select-none ${
        collapsed ? 'w-20' : 'w-64'
      }`}
    >
      {/* Логотип */}
      <div className="h-16 flex items-center justify-between px-4 border-b border-gray-800/50">
        <div className="flex items-center space-x-2 overflow-hidden">
          <span className="text-2xl flex-shrink-0">🚜</span>
          <span
            className={`font-bold text-lg whitespace-nowrap transition-all duration-300 ${
              collapsed ? 'opacity-0 w-0' : 'opacity-100'
            }`}
          >
            СпецТехника
          </span>
        </div>
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="text-gray-400 hover:text-white p-1.5 rounded-lg hover:bg-gray-800 transition-all duration-200 flex-shrink-0"
          title={collapsed ? 'Развернуть' : 'Свернуть'}
        >
          <svg
            className={`w-4 h-4 transition-transform duration-300 ${collapsed ? 'rotate-180' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
          </svg>
        </button>
      </div>

      {/* Меню */}
      <nav className="flex-1 overflow-y-auto py-3 scrollbar-thin scrollbar-thumb-gray-700 scrollbar-track-transparent">
        {Object.entries(groups).map(([groupName, items]) => (
          <div key={groupName} className="mb-2">
            {/* Заголовок группы */}
            <div
              className={`transition-all duration-300 overflow-hidden ${
                collapsed ? 'h-0 opacity-0' : 'h-8 opacity-100'
              }`}
            >
              <div className="px-4 pt-3 pb-1 text-[10px] uppercase tracking-wider text-gray-500 font-semibold">
                {groupName}
              </div>
            </div>

            {/* Пункты меню */}
            {items.map((item) => {
              const active = isActive(item.path);
              const hovered = hoveredItem === item.path;

              return (
                <div key={item.path} className="relative">
                  <button
                    onClick={() => navigate(item.path)}
                    onMouseEnter={() => setHoveredItem(item.path)}
                    onMouseLeave={() => setHoveredItem(null)}
                    className={`w-full flex items-center px-3 py-2.5 mx-1 rounded-lg text-sm transition-all duration-200 relative group ${
                      collapsed ? 'justify-center' : ''
                    } ${
                      active
                        ? 'bg-blue-600/90 text-white shadow-lg shadow-blue-600/20'
                        : 'text-gray-400 hover:bg-gray-800/60 hover:text-gray-100'
                    }`}
                  >
                    {/* Индикатор активного пункта (полоска слева) */}
                    {active && !collapsed && (
                      <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-blue-400 rounded-r-full" />
                    )}

                    <span
                      className={`text-lg transition-transform duration-200 flex-shrink-0 ${
                        hovered && !active ? 'scale-110' : ''
                      }`}
                    >
                      {item.icon}
                    </span>

                    {!collapsed && (
                      <span className="ml-3 whitespace-nowrap font-medium">{item.label}</span>
                    )}
                  </button>

                  {/* Тултип при сворачивании */}
                  {collapsed && hovered && (
                    <div className="absolute left-full top-1/2 -translate-y-1/2 ml-2 px-3 py-1.5 bg-gray-800 text-white text-xs rounded-lg shadow-xl z-50 whitespace-nowrap animate-in fade-in slide-in-from-left-1 duration-150">
                      {item.label}
                      {/* Стрелочка */}
                      <div className="absolute right-full top-1/2 -translate-y-1/2 border-4 border-transparent border-r-gray-800" />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Профиль пользователя */}
      <div className="border-t border-gray-800/50 p-3">
        <div className={`flex items-center ${collapsed ? 'justify-center' : 'space-x-3'}`}>
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center font-bold text-sm flex-shrink-0 ring-2 ring-gray-800">
            {user?.email?.charAt(0).toUpperCase() || '?'}
          </div>
          {!collapsed && (
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium truncate text-gray-200">
                {user?.email?.split('@')[0] || 'User'}
              </div>
              <button
                onClick={logout}
                className="text-xs text-gray-500 hover:text-red-400 transition-colors duration-200"
              >
                Выйти
              </button>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;