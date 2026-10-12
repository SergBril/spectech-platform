import React, { createContext, useContext, ReactNode } from 'react';

interface WebSocketContextType {
  lastMessage: MessageEvent | null;
  ws: WebSocket | null;
  connect: () => void;
  disconnect: () => void;
  sendMessage: (data: any) => void;
  connected: boolean;
}

const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined);

export const WebSocketProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  // 🚫 WebSocket полностью отключён для стабильности
  return (
    <WebSocketContext.Provider
      value={{
        lastMessage: null,
        ws: null,
        connect: () => {},
        disconnect: () => {},
        sendMessage: () => {},
        connected: false,
      }}
    >
      {children}
    </WebSocketContext.Provider>
  );
};

export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) throw new Error('useWebSocket must be used within WebSocketProvider');
  return context;
};