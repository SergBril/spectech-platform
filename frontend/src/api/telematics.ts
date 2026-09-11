import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

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
    const token = localStorage.getItem('access_token');
    const response = await axios.get<DashboardSummary>(
      `${API_URL}/telematics/dashboard/summary`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      }
    );
    return response.data;
  },
};
