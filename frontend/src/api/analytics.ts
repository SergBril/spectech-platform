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
  async getRevenueChart(months: number = 12): Promise<RevenueChartData[]> {
    const response = await apiClient.get<RevenueChartData[]>('/analytics/revenue-chart', {
      params: { months },
    });
    return response.data;
  },

  async getStatusChart(): Promise<StatusChartData[]> {
    const response = await apiClient.get<StatusChartData[]>('/analytics/status-chart');
    return response.data;
  },

  async getTopRequests(limit: number = 5): Promise<TopRequestData[]> {
    const response = await apiClient.get<TopRequestData[]>('/analytics/top-requests', {
      params: { limit },
    });
    return response.data;
  },

  async getSparkline(days: number = 7): Promise<SparklineData[]> {
    const response = await apiClient.get<SparklineData[]>('/analytics/sparkline', {
      params: { days },
    });
    return response.data;
  },
};
