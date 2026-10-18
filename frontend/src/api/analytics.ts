import apiClient from './client';

export interface RevenueChartData {
  month: string;
  total: number;
  paid: number;
  outstanding: number;
}

export interface StatusChartData {
  name: string;
  value: number;
  color: string;
}

export interface TopRequestData {
  id: number;
  work_type: string;
  address: string;
  amount: number;
}

export interface SparklineData {
  date: string;
  total: number;
}

export const analyticsApi = {
  async getRevenueChart(months: number = 12, dateFrom?: string, dateTo?: string): Promise<RevenueChartData[]> {
    const params: Record<string, any> = { months };
    if (dateFrom) params.date_from = dateFrom;
    if (dateTo) params.date_to = dateTo;
    const response = await apiClient.get<RevenueChartData[]>('/analytics/revenue-chart', { params });
    return response.data;
  },

  async getStatusChart(dateFrom?: string, dateTo?: string): Promise<StatusChartData[]> {
    const params: Record<string, any> = {};
    if (dateFrom) params.date_from = dateFrom;
    if (dateTo) params.date_to = dateTo;
    const response = await apiClient.get<StatusChartData[]>('/analytics/status-chart', { params });
    return response.data;
  },

  async getTopRequests(limit: number = 5, dateFrom?: string, dateTo?: string): Promise<TopRequestData[]> {
    const params: Record<string, any> = { limit };
    if (dateFrom) params.date_from = dateFrom;
    if (dateTo) params.date_to = dateTo;
    const response = await apiClient.get<TopRequestData[]>('/analytics/top-requests', { params });
    return response.data;
  },

  async getSparkline(days: number = 7): Promise<SparklineData[]> {
    const response = await apiClient.get<SparklineData[]>('/analytics/sparkline', {
      params: { days },
    });
    return response.data;
  },
};
