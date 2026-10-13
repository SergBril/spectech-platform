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
};