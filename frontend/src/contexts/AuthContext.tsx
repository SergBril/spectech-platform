import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { loginApi } from '../api/auth';

interface AuthContextType {
  token: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(
    localStorage.getItem('access_token')
  );
  const [refreshToken, setRefreshToken] = useState<string | null>(
    localStorage.getItem('refresh_token')
  );

  // Логируем начальное состояние
  useEffect(() => {
    console.log('🔐 AuthContext initialized:', {
      hasToken: !!token,
      hasRefreshToken: !!refreshToken
    });
  }, []);

  const login = async (email: string, password: string) => {
    console.log('🔄 Attempting login for:', email);

    try {
      const res = await loginApi(email, password);
      console.log('✅ Login API response:', res);

      // Сохраняем в localStorage
      localStorage.setItem('access_token', res.access_token);
      localStorage.setItem('refresh_token', res.refresh_token);

      console.log('💾 Tokens saved to localStorage');

      // Обновляем состояние
      setToken(res.access_token);
      setRefreshToken(res.refresh_token);

      console.log('✅ State updated, isAuthenticated will be true');
    } catch (error) {
      console.error('❌ Login failed:', error);
      throw error;
    }
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setToken(null);
    setRefreshToken(null);
    console.log('🚪 Logged out');
  };

  return (
    <AuthContext.Provider
      value={{
        token,
        refreshToken,
        isAuthenticated: !!token,
        login,
        logout
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
};
