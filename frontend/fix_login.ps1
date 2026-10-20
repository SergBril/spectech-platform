$content = @'
import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function LoginPage() {
  const [email, setEmail] = useState('admin@spectech.dev');
  const [password, setPassword] = useState('admin123');
  const [error, setError] = useState('');
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    try {
      await login(email, password);
      navigate('/');
    } catch (err: any) {
      setError('Неверный email или пароль');
      console.error(err);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <form onSubmit={handleSubmit} className="bg-white p-8 rounded-lg shadow-md w-96 border border-gray-200">
        <h2 className="text-2xl font-bold mb-6 text-center text-gray-800">🚜 СпецТехника Про</h2>
        {error && <p className="text-red-500 text-sm mb-4 bg-red-50 p-2 rounded">{error}</p>}

        <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
        <input
          type="email"
          value={email}
          onChange={e => setEmail(e.target.value)}
          className="w-full p-2 border border-gray-300 rounded mb-4 focus:ring-2 focus:ring-blue-500 outline-none"
          required
        />

        <label className="block text-sm font-medium text-gray-700 mb-1">Пароль</label>
        <input
          type="password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          className="w-full p-2 border border-gray-300 rounded mb-6 focus:ring-2 focus:ring-blue-500 outline-none"
          required
        />

        <button
          type="submit"
          className="w-full bg-blue-600 text-white p-2 rounded hover:bg-blue-700 transition font-semibold"
        >
          Войти в систему
        </button>

        <p className="mt-4 text-center text-sm text-gray-600">
          Нет аккаунта?{' '}
          <Link to="/register" className="font-medium text-blue-600 hover:text-blue-500">
            Зарегистрироваться
          </Link>
        </p>
        <p className="mt-2 text-center text-sm text-gray-600">
          <Link to="/forgot-password" className="font-medium text-blue-600 hover:text-blue-500">
            Забыли пароль?
          </Link>
        </p>
      </form>
    </div>
  );
}
'@

Set-Content -Path "src/pages/LoginPage.tsx" -Value $content -Encoding UTF8
Write-Host "✅ Fixed LoginPage.tsx" -ForegroundColor Green
