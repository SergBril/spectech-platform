import React, { useEffect, useState, useRef } from 'react';
import { notificationsApi, type Notification } from '../api/notifications';
import { useWebSocket } from '../contexts/WebSocketContext';

export const NotificationBell: React.FC = () => {
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [animate, setAnimate] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const { lastMessage } = useWebSocket();

  // Загружаем количество непрочитанных
  useEffect(() => {
    loadUnreadCount();
    const interval = setInterval(loadUnreadCount, 30000);
    return () => clearInterval(interval);
  }, []);

  // Слушаем WebSocket сообщения
  useEffect(() => {
    if (lastMessage?.type === 'new_notification') {
      setUnreadCount((prev) => prev + 1);
      setNotifications((prev) => [lastMessage.data, ...prev].slice(0, 20));
      // Пульсация при новом уведомлении
      setAnimate(true);
      setTimeout(() => setAnimate(false), 1000);
    }
  }, [lastMessage]);

  // Закрытие по Escape и клику вне
  useEffect(() => {
    if (!isOpen) return;

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsOpen(false);
    };

    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('keydown', handleEscape);
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  const loadUnreadCount = async () => {
    try {
      const data = await notificationsApi.getUnreadCount();
      setUnreadCount(data.count);
    } catch {
      // Тихая ошибка для фонового polling
    }
  };

  const loadNotifications = async () => {
    try {
      const data = await notificationsApi.getAll(false, 20);
      setNotifications(data);
    } catch (err) {
      console.error('Failed to load notifications:', err);
    }
  };

  const handleToggle = () => {
    if (!isOpen) loadNotifications();
    setIsOpen(!isOpen);
  };

  const handleMarkRead = async (id: number) => {
    try {
      await notificationsApi.markRead(id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      );
      setUnreadCount((prev) => Math.max(0, prev - 1));
    } catch (err) {
      console.error('Failed to mark read:', err);
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await notificationsApi.markAllRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch (err) {
      console.error('Failed to mark all read:', err);
    }
  };

  const formatTime = (iso: string) => {
    const date = new Date(iso);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return 'только что';
    if (minutes < 60) return `${minutes} мин назад`;
    if (hours < 24) return `${hours} ч назад`;
    return `${days} дн назад`;
  };

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Кнопка колокольчика */}
      <button
        onClick={handleToggle}
        className={`relative p-2 rounded-lg text-gray-500 hover:text-gray-700 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all duration-200 ${
          animate ? 'scale-110' : ''
        }`}
        title="Уведомления"
        aria-label={`Уведомления${unreadCount > 0 ? ` (${unreadCount} непрочитанных)` : ''}`}
      >
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
          />
        </svg>

        {/* Бейдж с анимацией пульсации */}
        {unreadCount > 0 && (
          <span className="absolute top-0.5 right-0.5 inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 text-[10px] font-bold leading-none text-white bg-red-500 rounded-full ring-2 ring-white">
            <span className={animate ? 'animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75' : ''} />
            <span className="relative">{unreadCount > 99 ? '99+' : unreadCount}</span>
          </span>
        )}
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-[340px] sm:w-96 bg-white rounded-xl shadow-xl border border-gray-100 z-50 max-h-[500px] overflow-hidden flex flex-col animate-in fade-in slide-in-from-top-2 duration-200">
          {/* Header */}
          <div className="p-4 border-b border-gray-100 flex justify-between items-center bg-gradient-to-r from-blue-50 to-white">
            <div className="flex items-center gap-2">
              <span className="text-lg">🔔</span>
              <h3 className="text-base font-semibold text-gray-900">Уведомления</h3>
              {unreadCount > 0 && (
                <span className="bg-red-100 text-red-700 text-xs font-medium px-2 py-0.5 rounded-full">
                  {unreadCount}
                </span>
              )}
            </div>
            {unreadCount > 0 && (
              <button
                onClick={handleMarkAllRead}
                className="text-xs text-blue-600 hover:text-blue-800 font-medium px-2 py-1 rounded hover:bg-blue-50 transition-colors"
              >
                Прочитать все
              </button>
            )}
          </div>

          {/* Список */}
          <div className="overflow-y-auto flex-1">
            {notifications.length === 0 ? (
              <div className="p-10 text-center">
                <div className="text-5xl mb-3 opacity-50">🔕</div>
                <p className="text-gray-500 font-medium">Нет уведомлений</p>
                <p className="text-xs text-gray-400 mt-1">Новые уведомления появятся здесь</p>
              </div>
            ) : (
              <ul className="divide-y divide-gray-50">
                {notifications.map((notif) => (
                  <li
                    key={notif.id}
                    className={`p-4 cursor-pointer transition-colors duration-150 ${
                      !notif.is_read
                        ? 'bg-blue-50/50 hover:bg-blue-50'
                        : 'hover:bg-gray-50'
                    }`}
                    onClick={() => !notif.is_read && handleMarkRead(notif.id)}
                  >
                    <div className="flex justify-between items-start gap-3">
                      <div className="flex-1 min-w-0">
                        <p className={`text-sm font-medium truncate ${
                          !notif.is_read ? 'text-gray-900' : 'text-gray-600'
                        }`}>
                          {notif.title}
                        </p>
                        <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">
                          {notif.body}
                        </p>
                        <p className="text-[10px] text-gray-400 mt-1.5">
                          {formatTime(notif.sent_at)}
                        </p>
                      </div>
                      {!notif.is_read && (
                        <span className="w-2 h-2 bg-blue-500 rounded-full flex-shrink-0 mt-1.5 ring-2 ring-blue-200" />
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Footer */}
          {notifications.length > 0 && (
            <div className="p-2 border-t border-gray-100 bg-gray-50 text-center">
              <button
                onClick={() => setIsOpen(false)}
                className="text-xs text-gray-500 hover:text-gray-700 px-3 py-1 rounded hover:bg-gray-200 transition-colors"
              >
                Закрыть
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default NotificationBell;