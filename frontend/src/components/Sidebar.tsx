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
  
  { label: 'Маркетплейс', icon: '🎯', path: '/marketplace', group: 'Бизнес' },
  { label: 'Мои публикации', icon: '🏪', path: '/my-listings', group: 'Бизнес' },
  { label: 'Контрагенты', icon: '👥', path: '/contractors', group: 'Бизнес' },
  
  { label: 'Топливо', icon: '⛽', path: '/fuel/analytics', group: 'Эксплуатация' },
  { label: 'ТО и Ремонты', icon: '🔧', path: '/maintenance', group: 'Эксплуатация' },
  { label: 'Сверки', icon: '📊', path: '/reconciliation', group: 'Эксплуатация' },
  
  { label: 'Финансы', icon: '💰', path: '/finance', group: 'Финансы' },
  { label: 'Счета', icon: '📄', path: '/invoices', group: 'Финансы' },
  
  { label: 'Email шаблоны', icon: '📧', path: '/email-templates', group: 'Система' },
  { label: 'Email логи', icon: '📨', path: '/email-logs', group: 'Система' },
  { label: 'Настройки', icon: '⚙️', path: '/settings/company', group: 'Система' },
];

export const Sidebar: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const [collapsed, setCollapsed] = useState(false);

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
      className={`fixed left-0 top-0 h-screen bg-gray-900 text-white flex flex-col transition-all duration-300 z-40 ${
        collapsed ? 'w-20' : 'w-64'
      }`}
    >
      {/* Логотип */}
      <div className="h-16 flex items-center justify-between px-4 border-b border-gray-800">
        {!collapsed && (
          <div className="flex items-center space-x-2">
            <span className="text-2xl">🚜</span>
            <span className="font-bold text-lg">СпецТехника</span>
          </div>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="text-gray-400 hover:text-white p-2 rounded hover:bg-gray-800"
          title={collapsed ? 'Развернуть' : 'Свернуть'}
        >
          {collapsed ? '→' : '←'}
        </button>
      </div>

      {/* Меню */}
      <nav className="flex-1 overflow-y-auto py-4">
        {Object.entries(groups).map(([groupName, items]) => (
          <div key={groupName} className="mb-4">
            {!collapsed && (
              <div className="px-4 mb-2 text-xs uppercase text-gray-500 font-semibold">
                {groupName}
              </div>
            )}
            {items.map((item) => (
              <button
                key={item.path}
                onClick={() => navigate(item.path)}
                className={`w-full flex items-center px-4 py-3 text-sm transition-colors ${
                  isActive(item.path)
                    ? 'bg-blue-600 text-white border-r-4 border-blue-400'
                    : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                }`}
                title={collapsed ? item.label : ''}
              >
                <span className="text-xl">{item.icon}</span>
                {!collapsed && <span className="ml-3">{item.label}</span>}
              </button>
            ))}
          </div>
        ))}
      </nav>

      {/* Профиль пользователя */}
      <div className="border-t border-gray-800 p-4">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-full bg-blue-600 flex items-center justify-center font-bold">
            {user?.email?.charAt(0).toUpperCase()}
          </div>
          {!collapsed && (
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium truncate">{user?.email}</div>
              <button
                onClick={logout}
                className="text-xs text-gray-400 hover:text-red-400"
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