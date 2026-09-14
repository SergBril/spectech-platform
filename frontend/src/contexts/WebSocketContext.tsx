// frontend/src/contexts/WebSocketContext.tsx
import React, { createContext, useContext, useEffect, useRef, useState, ReactNode, useCallback } from 'react';
import { useAuth } from './AuthContext';

// ==================== ТИПЫ ====================

type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

interface WebSocketContextType {
  lastMessage: any;
  isConnected: boolean;
  status: ConnectionStatus;
  reconnectAttempts: number;
  sendMessage: (message: any) => boolean;
}

interface WebSocketConfig {
  maxReconnectAttempts: number;
  reconnectInterval: number; // мс
  maxReconnectInterval: number; // мс
  heartbeatInterval: number; // мс
  heartbeatTimeout: number; // мс
}

// ==================== КОНФИГУРАЦИЯ ====================

const DEFAULT_CONFIG: WebSocketConfig = {
  maxReconnectAttempts: 10,
  reconnectInterval: 1000, // 1 сек
  maxReconnectInterval: 30000, // 30 сек (exponential backoff)
  heartbeatInterval: 25000, // 25 сек (меньше чем таймаут прокси 60 сек)
  heartbeatTimeout: 5000, // 5 сек
};

// ==================== КОНТЕКСТ ====================

const WebSocketContext = createContext<WebSocketContextType>({
  lastMessage: null,
  isConnected: false,
  status: 'disconnected',
  reconnectAttempts: 0,
  sendMessage: () => false,
});

export const useWebSocket = () => useContext(WebSocketContext);

// ==================== ПРОВАЙДЕР ====================

interface Props {
  children: ReactNode;
  config?: Partial<WebSocketConfig>;
}

export const WebSocketProvider: React.FC<Props> = ({ children, config = {} }) => {
  const { user } = useAuth();
  const mergedConfig = { ...DEFAULT_CONFIG, ...config };

  // Состояние
  const [lastMessage, setLastMessage] = useState<any>(null);
  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const [reconnectAttempts, setReconnectAttempts] = useState(0);

  // Refs (не вызывают re-render)
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const heartbeatIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const heartbeatTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const isMountedRef = useRef(true); // Защита от StrictMode
  const shouldReconnectRef = useRef(true);

  // ==================== УТИЛИТЫ ====================

  const clearTimers = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
      heartbeatIntervalRef.current = null;
    }
    if (heartbeatTimeoutRef.current) {
      clearTimeout(heartbeatTimeoutRef.current);
      heartbeatTimeoutRef.current = null;
    }
  }, []);

  const getWsUrl = useCallback((): string | null => {
    const token = localStorage.getItem('access_token');
    if (!token) return null;

    // Определяем протокол автоматически
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = import.meta.env.VITE_API_HOST || window.location.host;
    return `${protocol}//${host}/api/v1/ws?token=${token}`;
  }, []);

  // ==================== HEARTBEAT ====================

  const startHeartbeat = useCallback(() => {
    clearTimers();

    // Отправляем ping каждые N секунд
    heartbeatIntervalRef.current = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        const pingMessage = JSON.stringify({ type: 'ping', timestamp: Date.now() });
        wsRef.current.send(pingMessage);

        // Таймаут ожидания pong
        heartbeatTimeoutRef.current = setTimeout(() => {
          console.warn('⏱️ WebSocket heartbeat timeout, reconnecting...');
          wsRef.current?.close(4000, 'Heartbeat timeout');
        }, mergedConfig.heartbeatTimeout);
      }
    }, mergedConfig.heartbeatInterval);
  }, [mergedConfig.heartbeatInterval, mergedConfig.heartbeatTimeout, clearTimers]);

  // ==================== ПОДКЛЮЧЕНИЕ ====================

  const connect = useCallback(() => {
    if (!isMountedRef.current) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const wsUrl = getWsUrl();
    if (!wsUrl) {
      console.warn('⚠️ WebSocket: нет токена для подключения');
      setStatus('disconnected');
      return;
    }

    setStatus('connecting');

    try {
      const socket = new WebSocket(wsUrl);
      wsRef.current = socket;

      // ---- ON OPEN ----
      socket.onopen = () => {
        if (!isMountedRef.current) {
          socket.close();
          return;
        }
        console.log('✅ WebSocket connected');
        setStatus('connected');
        setReconnectAttempts(0);
        reconnectAttemptsRef.current = 0;
        startHeartbeat();
      };

      // ---- ON MESSAGE ----
      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);

          // Обработка pong от сервера
          if (message.type === 'pong') {
            if (heartbeatTimeoutRef.current) {
              clearTimeout(heartbeatTimeoutRef.current);
              heartbeatTimeoutRef.current = null;
            }
            return;
          }

          setLastMessage(message);
        } catch (err) {
          console.error('❌ Failed to parse WebSocket message:', err);
        }
      };

      // ---- ON CLOSE ----
      socket.onclose = (event) => {
        if (!isMountedRef.current) return;

        clearTimers();

        const reason = event.reason || 'Unknown reason';
        const wasClean = event.wasClean;

        console.log(
          `❌ WebSocket closed: code=${event.code}, reason=${reason}, clean=${wasClean}`
        );

        setStatus('disconnected');
        wsRef.current = null;

        // Коды, при которых НЕ нужно переподключаться
        const noReconnectCodes = [1000, 1001, 4001, 4003]; // нормальное закрытие, auth failed
        const shouldReconnect =
          shouldReconnectRef.current &&
          !noReconnectCodes.includes(event.code) &&
          reconnectAttemptsRef.current < mergedConfig.maxReconnectAttempts;

        if (shouldReconnect) {
          // Exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s (max)
          const delay = Math.min(
            mergedConfig.reconnectInterval * Math.pow(2, reconnectAttemptsRef.current),
            mergedConfig.maxReconnectInterval
          );

          console.log(
            `🔄 Reconnecting in ${delay / 1000}s (attempt ${reconnectAttemptsRef.current + 1}/${mergedConfig.maxReconnectAttempts})`
          );

          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttemptsRef.current += 1;
            setReconnectAttempts(reconnectAttemptsRef.current);
            connect();
          }, delay);
        } else if (reconnectAttemptsRef.current >= mergedConfig.maxReconnectAttempts) {
          console.error('🚫 Max reconnect attempts reached');
          setStatus('error');
        }
      };

      // ---- ON ERROR ----
      socket.onerror = (error) => {
        console.error('🚨 WebSocket error:', error);
        setStatus('error');
      };
    } catch (err) {
      console.error('🚨 Failed to create WebSocket:', err);
      setStatus('error');
    }
  }, [getWsUrl, startHeartbeat, clearTimers, mergedConfig]);

  // ==================== ОТПРАВКА СООБЩЕНИЙ ====================

  const sendMessage = useCallback((message: any): boolean => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      try {
        wsRef.current.send(JSON.stringify(message));
        return true;
      } catch (err) {
        console.error('Failed to send message:', err);
        return false;
      }
    }
    return false;
  }, []);

  // ==================== ЭФФЕКТЫ ====================

  // Подключение при появлении пользователя
  useEffect(() => {
    isMountedRef.current = true;
    shouldReconnectRef.current = true;

    if (user) {
      connect();
    }

    return () => {
      isMountedRef.current = false;
      shouldReconnectRef.current = false;
      clearTimers();

      if (wsRef.current) {
        wsRef.current.close(1000, 'Component unmounted');
        wsRef.current = null;
      }
    };
  }, [user, connect, clearTimers]);

  // Обработка онлайн/офлайн браузера
  useEffect(() => {
    const handleOnline = () => {
      console.log('🌐 Browser online, reconnecting...');
      if (wsRef.current?.readyState !== WebSocket.OPEN) {
        reconnectAttemptsRef.current = 0;
        connect();
      }
    };

    const handleOffline = () => {
      console.log('📴 Browser offline');
      setStatus('disconnected');
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, [connect]);

  // ==================== РЕНДЕР ====================

  return (
    <WebSocketContext.Provider
      value={{
        lastMessage,
        isConnected: status === 'connected',
        status,
        reconnectAttempts,
        sendMessage,
      }}
    >
      {children}
    </WebSocketContext.Provider>
  );
};
