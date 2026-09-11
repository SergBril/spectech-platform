import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { loginApi } from '../api/auth';
import axios from 'axios';

interface User {
  id: number;
  email: string;
  full_name: string;
  is_superuser: boolean;
  role?: string;
}

interface AuthContextType {
  token: string | null;
  user: User | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  hasPermission: (entity: string, action: string) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(
    localStorage.getItem('access_token')
  );
  const [user, setUser] = useState<User | null>(null);
  const [permissions, setPermissions] = useState<string[]>([]);

  // Функция для загрузки данных пользователя
  const loadUserData = async (accessToken: string) => {
    try {
      // Загружаем профиль пользователя
      const meResponse = await axios.get(`${API_URL}/me/me`, {
        headers: { Authorization: `Bearer ${accessToken}` }
      });
      setUser(meResponse.data);

      // Загружаем права пользователя
      const permsResponse = await axios.get(`${API_URL}/me/me/permissions`, {
        headers: { Authorization: `Bearer ${accessToken}` }
      });
      setPermissions(permsResponse.data || []);

      console.log('✅ User data loaded:', meResponse.data);
    } catch (error) {
      console.error('❌ Failed to load user data:', error);
    }
  };

  // При инициализации загружаем данные, если есть токен
  useEffect(() => {
    if (token) {
      loadUserData(token);
    }
  }, [token]);

const login = async (email: string, password: string) => {
  console.log('🔄 Attempting login for:', email);

  try {
    const res = await loginApi(email, password);
    console.log('✅ Login API response:', res);

    // Сохраняем токены
    localStorage.setItem('access_token', res.access_token);
    localStorage.setItem('refresh_token', res.refresh_token);

    console.log('💾 Tokens saved to localStorage');

    // Обновляем состояние токена (useEffect вызовет loadUserData автоматически)
    setToken(res.access_token);

    console.log('✅ Login complete');
  } catch (error) {
    console.error('❌ Login failed:', error);
    throw error;
  }
};

  const logout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setToken(null);
    setUser(null);
    setPermissions([]);
    console.log('🚪 Logged out');
  };

  // Функция проверки прав
  const hasPermission = (entity: string, action: string): boolean => {
    // Superuser имеет все права
    if (user?.is_superuser) {
      return true;
    }
    // Проверяем, есть ли право в списке
    return permissions.includes(`${entity}:${action}`);
  };

  return (
    <AuthContext.Provider
      value={{
        token,
        user,
        isAuthenticated: !!token,
        login,
        logout,
        hasPermission
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
