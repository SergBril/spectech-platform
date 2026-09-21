import React, { createContext, useContext, useEffect, useRef, useCallback, ReactNode } from 'react';
import { useAuth } from './AuthContext';

interface WebSocketContextType {
  ws: WebSocket | null;
  connect: () => void;
  disconnect: () => void;
  sendMessage: (data: any) => void;
}

const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined);

export const WebSocketProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const { token, isAuthenticated } = useAuth();
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const isConnectingRef = useRef(false);

  const connect = useCallback(() => {
    if (!isAuthenticated || !token) {
      console.log('⏸️ WebSocket: not authenticated, skip connect');
      return;
    }

    if (isConnectingRef.current) {
      console.log('⏸️ WebSocket: already connecting, skip');
      return;
    }

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      console.log('⏸️ WebSocket: already connected, skip');
      return;
    }

    isConnectingRef.current = true;
    const wsUrl = `ws://localhost:8000/api/v1/ws?token=${token}`;
    console.log('🔌 WebSocket: connecting to', wsUrl);

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('✅ WebSocket: connected');
      isConnectingRef.current = false;
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('📨 WebSocket message:', data);
      } catch (e) {
        console.error('❌ WebSocket: failed to parse message', e);
      }
    };

    ws.onerror = (error) => {
      console.error('❌ WebSocket error:', error);
      isConnectingRef.current = false;
    };

    ws.onclose = (event) => {
      console.log(`🔌 WebSocket closed: code=${event.code}, reason=${event.reason}`);
      isConnectingRef.current = false;
      wsRef.current = null;

      if (event.code !== 1000 && isAuthenticated) {
        console.log('🔄 WebSocket: scheduling reconnect in 5 seconds...');
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, 5000);
      }
    };
  }, [token, isAuthenticated]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      console.log('🔌 WebSocket: disconnecting...');
      wsRef.current.close(1000, 'User logout');
      wsRef.current = null;
    }

    isConnectingRef.current = false;
  }, []);

  const sendMessage = useCallback((data: any) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    } else {
      console.warn('⚠️ WebSocket: not connected, cannot send message');
    }
  }, []);

  useEffect(() => {
    if (isAuthenticated && token) {
      connect();
    }
    return () => {
      disconnect();
    };
  }, [isAuthenticated, token, connect, disconnect]);

  useEffect(() => {
    if (!isAuthenticated) {
      disconnect();
    }
  }, [isAuthenticated, disconnect]);

  return (
    <WebSocketContext.Provider value={{ ws: wsRef.current, connect, disconnect, sendMessage }}>
      {children}
    </WebSocketContext.Provider>
  );
};

export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) throw new Error('useWebSocket must be used within WebSocketProvider');
  return context;
};
