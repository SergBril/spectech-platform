import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { showToast } from '../../utils/toast';
import apiClient from '../../api/client';

export const DriverLoginPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setLoading(true);
      const res = await apiClient.post('/auth/login', { email, password });
      localStorage.setItem('access_token', res.data.access_token);
      localStorage.setItem('refresh_token', res.data.refresh_token);
      showToast.success('✅ Вход выполнен');
      navigate('/driver/dashboard');
    } catch (err: any) {
      showToast.error('Ошибка входа: ' + (err?.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-900 to-blue-700 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl p-8 w-full max-w-sm">
        <div className="text-center mb-6">
          <div className="text-4xl mb-2">🚜</div>
          <h1 className="text-2xl font-bold text-gray-900">СпецТехника</h1>
          <p className="text-gray-500 text-sm mt-1">Вход для водителей</p>
        </div>

        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full border border-gray-300 rounded-lg px-4 py-3 text-base focus:ring-2 focus:ring-blue-500 outline-none"
              placeholder="driver@example.com"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Пароль</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full border border-gray-300 rounded-lg px-4 py-3 text-base focus:ring-2 focus:ring-blue-500 outline-none"
              placeholder="••••••••"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 text-white py-3 rounded-lg font-semibold text-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
          >
            {loading ? '⏳ Вход...' : 'Войти'}
          </button>
        </form>

        <div className="mt-6 text-center">
          <a href="/" className="text-sm text-blue-600 hover:underline">← На главную</a>
        </div>
      </div>
    </div>
  );
};

export default DriverLoginPage;