import axios from 'axios';
// Если showToast не импортирован, раскомментируйте строку ниже и укажите правильный путь:
// import { showToast } from '../utils/toast';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'; // Исправил порт на 8000, так как в логах был он

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

        // Проверка на наличие showToast, чтобы не упало, если он не импортирован
        alert('Сессия истекла. Войдите снова.');

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

// ============================================================
// Типы и API для отзывов (Reviews)
// ============================================================

export interface CompanyReview {
  id: number;
  company_id: number;
  reviewer_contractor_id: number;
  reviewer_contractor_name: string;
  reviewer_user_id?: number;
  request_id?: number;
  rating: number;
  comment: string;
  response?: string;
  responded_at?: string;
  is_verified: boolean;
  is_public: boolean;
  created_at: string;
  updated_at: string;
}

export interface CompanyRatingSummary {
  company_id: number;
  company_name: string;
  average_rating: number;
  total_reviews: number;
  rating_distribution: Record<string, number>;
}

export interface CreateReviewRequest {
  company_id: number;
  rating: number;
  comment: string;
  request_id?: number;
}

// ✅ ИСПРАВЛЕНО: Оставлен только один, полный и корректный объект reviewsApi
export const reviewsApi = {
  // === Публичные endpoints ===

  async getCompanyReviews(
    companyId: number,
    limit = 20,
    offset = 0,
    minRating?: number
  ): Promise<{ items: any[]; total: number }> {
    const response = await apiClient.get(`/public/companies/${companyId}/reviews`, {
      params: { limit, offset, min_rating: minRating }
    });
    return response.data;
  },

  async getCompanyRating(companyId: number): Promise<{
    company_id: number;
    company_name: string;
    average_rating: number | null;
    total_reviews: number;
    distribution: Record<string, number>;
    category_averages: Record<string, number | null>;
  }> {
    const response = await apiClient.get(`/public/companies/${companyId}/rating`);
    return response.data;
  },

  async markHelpful(reviewId: number): Promise<{ helpful_count: number }> {
    const response = await apiClient.post(`/public/reviews/${reviewId}/helpful`);
    return response.data;
  },

  // === Приватные endpoints ===

  async createReview(data: {
    rental_id: number;
    review_type: 'client_to_owner' | 'owner_to_client';
    rating: number;
    comment?: string;
    pros?: string;
    cons?: string;
    photos?: string[];
    quality_rating?: number;
    punctuality_rating?: number;
    communication_rating?: number;
    is_anonymous?: boolean;
  }): Promise<any> {
    const response = await apiClient.post('/reviews', data);
    return response.data;
  },

  async getMyReviews(limit = 50, offset = 0): Promise<{ items: any[]; total: number }> {
    const response = await apiClient.get('/reviews/my', { params: { limit, offset } });
    return response.data;
  },

  async canReview(rentalId: number): Promise<{
    rental_id: number;
    can_review_owner: boolean;
    can_review_client: boolean;
    has_reviewed_owner: boolean;
    has_reviewed_client: boolean;
  }> {
    const response = await apiClient.get(`/reviews/can-review/${rentalId}`);
    return response.data;
  },

  async updateReview(reviewId: number, data: any): Promise<any> {
    const response = await apiClient.patch(`/reviews/${reviewId}`, data);
    return response.data;
  },

  async deleteReview(reviewId: number): Promise<void> {
    await apiClient.delete(`/reviews/${reviewId}`);
  },

  async respondToReview(reviewId: number, responseText: string): Promise<CompanyReview> {
    const response = await apiClient.post(`/reviews/${reviewId}/respond`, { response: responseText });
    return response.data;
  }
};
