import apiClient from './client';

export interface PlatformStats {
  totals: { users: number; companies: number; vehicles: number; requests: number };
  new_in_period: { users: number; companies: number; vehicles: number; requests: number };
  vehicles_by_status: Record<string, number>;
  requests_by_status: Record<string, number>;
  period: { from: string; to: string };
}

export interface ProviderRequest {
  id: number;
  title: string;
  body: string;
  user_id: number;
  sent_at: string | null;
  is_read: boolean;
}

export interface ReviewsStats {
  total_reviews: number;
  approved_reviews: number;
  pending_reviews: number;
  avg_rating: number;
  avg_quality: number;
  avg_punctuality: number;
  avg_communication: number;
}

export interface FinanceStats {
  total_invoices: number;
  total_revenue: number;
  unpaid_amount: number;
  total_payments: number;
  period: { from: string; to: string };
}


export interface TopCompanies {
  top_by_requests: Array<{id: number; name: string; count: number}>;
  top_by_vehicles: Array<{id: number; name: string; count: number}>;
}

export interface UserActivity {
  new_today: number;
  new_this_week: number;
}

export const adminApi = {
  getStats: async (dateFrom?: string, dateTo?: string): Promise<PlatformStats> => {
    const params: Record<string, string> = {};
    if (dateFrom) params.date_from = dateFrom;
    if (dateTo) params.date_to = dateTo;
    const res = await apiClient.get('/admin/stats', { params });
    return res.data;
  },

  getProviderRequests: async (limit = 50): Promise<{ requests: ProviderRequest[] }> => {
    const res = await apiClient.get('/admin/provider-requests', { params: { limit } });
    return res.data;
  },

  getReviewsStats: async (): Promise<ReviewsStats> => {
    const res = await apiClient.get('/admin/reviews-stats');
    return res.data;
  },

  getFinanceStats: async (dateFrom?: string, dateTo?: string): Promise<FinanceStats> => {
    const params: Record<string, string> = {};
    if (dateFrom) params.date_from = dateFrom;
    if (dateTo) params.date_to = dateTo;
    const res = await apiClient.get('/admin/finance-stats', { params });
    return res.data;
  },
};
