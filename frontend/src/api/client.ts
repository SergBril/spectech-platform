import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080/api/v1';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor - добавляем токен и company_id
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  // 🆕 Добавляем X-Company-Id header для мульти-компании
  const companyId = localStorage.getItem('spectech_current_company_id');
  if (companyId) {
    config.headers['X-Company-Id'] = companyId;
  }

  return config;
});

// Response interceptor - auto refresh
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value?: any) => void;
  reject: (reason?: any) => void;
}> = [];

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Если 401 и это не повторная попытка
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const refreshToken = localStorage.getItem('refresh_token');
        
        if (!refreshToken) {
          console.warn('No refresh token, redirecting to login');
          localStorage.removeItem('access_token');
          window.location.href = '/login';
          return Promise.reject(error);
        }

        console.log('🔄 Attempting to refresh token...');
        
        // Попытка обновить токен
        const response = await axios.post(
          `${API_BASE_URL}/auth/refresh`,
          { refresh_token: refreshToken }
        );

        const { access_token, refresh_token: newRefreshToken } = response.data;
        
        localStorage.setItem('access_token', access_token);
        if (newRefreshToken) {
          localStorage.setItem('refresh_token', newRefreshToken);
        }
        
        console.log('✅ Token refreshed successfully');

        // Повторяем оригинальный запрос с новым токеном
        originalRequest.headers.Authorization = `Bearer ${access_token}`;
        return apiClient(originalRequest);
        
      } catch (refreshError: any) {
        console.error('❌ Refresh token failed:', refreshError.response?.data || refreshError.message);
        
        // Refresh не сработал — выходим
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        
        showToast.error('Сессия истекла. Войдите снова.');
        
        // Небольшая задержка перед редиректом, чтобы показать ошибку
        setTimeout(() => {
          window.location.href = '/login';
        }, 1500);
        
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

export default apiClient;
