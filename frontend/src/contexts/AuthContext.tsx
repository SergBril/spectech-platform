import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { authApi } from '../api/auth';
import apiClient from '../api/client';

interface User {
  id: number;
  email: string;
  full_name: string;
  is_superuser: boolean;
}

interface AuthContextType {
  user: User | null;
  permissions: string[];
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName: string, phone?: string) => Promise<void>;
  logout: () => void;
  hasPermission: (entity: string, action: string) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [permissions, setPermissions] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const loadUserData = async () => {
    try {
      // ВАЖНО: правильный путь /me/me (префикс роутера + эндпоинт)
      const meResponse = await apiClient.get('/me/me');
      setUser(meResponse.data);

      // Правильный путь /me/me/permissions
      const permsResponse = await apiClient.get('/me/me/permissions');
      setPermissions(permsResponse.data);
    } catch (error) {
      console.error('Ошибка загрузки профиля:', error);
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      setUser(null);
      setPermissions([]);
    }
  };

  useEffect(() => {
    const initAuth = async () => {
      const token = localStorage.getItem('access_token');
      if (token) {
        await loadUserData();
      }
      setIsLoading(false);
    };
    initAuth();
  }, []);

  const login = async (email: string, password: string) => {
    const response = await authApi.login({ email, password });
    const { access_token, refresh_token } = response.data;

    localStorage.setItem('access_token', access_token);
    localStorage.setItem('refresh_token', refresh_token);

    await loadUserData();
  };

  const register = async (email: string, password: string, fullName: string, phone?: string) => {
    await authApi.register({ email, password, full_name: fullName, phone });
    await login(email, password);
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setUser(null);
    setPermissions([]);
  };

  const hasPermission = (entity: string, action: string) => {
    if (user?.is_superuser) {
      return true;
    }
    return permissions.includes(`${entity}:${action}`);
  };

  const isAuthenticated = !!user;

  return (
    <AuthContext.Provider value={{
      user,
      permissions,
      isAuthenticated,
      isLoading,
      login,
      register,
      logout,
      hasPermission
    }}>
      {children}
    </AuthContext.Provider>
  );
};
