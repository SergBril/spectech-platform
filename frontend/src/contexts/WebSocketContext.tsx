import React, { createContext, useContext, ReactNode, useEffect, useRef, useState, useCallback } from 'react';

interface WebSocketContextType {
  lastMessage: any | null;
  ws: WebSocket | null;
  connect: () => void;
  disconnect: () => void;
  sendMessage: (data: any) => void;
  connected: boolean;
  subscribe: (type: string, handler: (data: any) => void) => () => void;
}

const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined);

export const WebSocketProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<any | null>(null);
  const subscribersRef = useRef<Map<string, Set<(data: any) => void>>>(new Map());
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const subscribe = useCallback((type: string, handler: (data: any) => void) => {
    if (!subscribersRef.current.has(type)) {
      subscribersRef.current.set(type, new Set());
    }
    subscribersRef.current.get(type)!.add(handler);
    return () => {
      subscribersRef.current.get(type)?.delete(handler);
    };
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const token = localStorage.getItem('access_token');
    if (!token) return;

    // Use Vite proxy in dev, direct connection in production
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/api/v1/ws?token=${token}`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('✅ WebSocket connected');
reconnectAttemptRef.current = 0;
      setConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setLastMessage(data);

        // Notify subscribers by message type
        const msgType = data.type || data.event;
        if (msgType && subscribersRef.current.has(msgType)) {
          subscribersRef.current.get(msgType)!.forEach(handler => handler(data));
        }
        // Also notify wildcard subscribers
        if (subscribersRef.current.has('*')) {
          subscribersRef.current.get('*')!.forEach(handler => handler(data));
        }
      } catch (e) {
        console.error('WS parse error:', e);
      }
    };

    ws.onclose = (e) => {
      console.log('❌ WebSocket closed:', e.code, e.reason);
      setConnected(false);
      wsRef.current = null;
      // Auto-reconnect after 5 seconds
      reconnectTimerRef.current = setTimeout(() => connect(), 5000);
    };

    ws.onerror = (e) => {
      console.error('WebSocket error:', e);
    };
  }, []);

  const disconnect = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setConnected(false);
  }, []);

  const sendMessage = useCallback((data: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  // Auto-connect on mount
  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  return (
    <WebSocketContext.Provider value={{ lastMessage, ws: wsRef.current, connect, disconnect, sendMessage, connected, subscribe }}>
      {children}
    </WebSocketContext.Provider>
  );
};

export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) throw new Error('useWebSocket must be used within WebSocketProvider');
  return context;
};
