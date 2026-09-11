import apiClient from './client';

export interface DashboardSummary {
  vehicles: {
    total: number;
    active: number;
    free?: number;
    busy?: number;
    maintenance?: number;
  };
  gps_points: {
    total: number;
    today: number;
  };
  alerts: {
    total: number;
    active: number;
    critical: number;
  };
  fuel: {
    total_volume: number;
    total_cost: number;
    week_volume: number;
    week_cost: number;
    drains_count: number;
  };
  updated_at: string;
}

export const telematicsApi = {
  async getDashboardSummary(): Promise<DashboardSummary> {
    const response = await apiClient.get<DashboardSummary>('/telematics/dashboard/summary');
    return response.data;
  },
};
