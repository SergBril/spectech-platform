import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { loginApi } from '../api/auth';
import apiClient from '../api/client';

interface User {
  id: number;
  email: string;
  full_name: string;
  phone?: string | null;
  company_id: number;  // ← ДОБАВИТЬ
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

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(
    localStorage.getItem('access_token')
  );
  const [user, setUser] = useState<User | null>(null);
  const [permissions, setPermissions] = useState<string[]>([]);
const loadUserData = async (accessToken: string) => {
  try {
    // ✅ ИСПРАВЛЕНО: /me вместо /me/me
    const meResponse = await apiClient.get('/me');
    setUser(meResponse.data);

    // ✅ ИСПРАВЛЕНО: /me/permissions вместо /me/me/permissions
    const permsResponse = await apiClient.get('/me/permissions');
    setPermissions(permsResponse.data || []);

    console.log('✅ User data loaded:', meResponse.data);
  } catch (error) {
    console.error('❌ Failed to load user data:', error);
  }
};

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

      localStorage.setItem('access_token', res.access_token);
      localStorage.setItem('refresh_token', res.refresh_token);

      console.log('💾 Tokens saved to localStorage');

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

  const hasPermission = (entity: string, action: string): boolean => {
    if (user?.is_superuser) {
      return true;
    }
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
