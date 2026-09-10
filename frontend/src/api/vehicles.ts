import apiClient from './client';

export interface Vehicle {
  id: number;
  id_type: string;
  id_value: string;
  name: string;
  year?: number;
  status: string;
  fuel_norm_per_hour?: string;
  fuel_norm_per_100km?: string;
  psm_number?: string;
  osago_expiry_date?: string;
  category_id?: number;
  owner_id?: number;
  company_id?: number;
  is_custom_number: boolean;
  created_at: string;
  updated_at: string;
}

export interface VehicleCreate {
  id_type: string;
  id_value: string;
  name: string;
  year?: number;
  status?: string;
  fuel_norm_per_hour?: number;
  fuel_norm_per_100km?: number;
  psm_number?: string;
  osago_expiry_date?: string;
  category_id?: number;
  owner_id?: number;
  company_id?: number;
}

export interface VehicleUpdate {
  id_type?: string;
  id_value?: string;
  name?: string;
  year?: number;
  status?: string;
  fuel_norm_per_hour?: number;
  fuel_norm_per_100km?: number;
  psm_number?: string;
  osago_expiry_date?: string;
  category_id?: number;
  owner_id?: number;
  company_id?: number;
}

export interface VehicleListResponse {
  items: Vehicle[];
  total: number;
}

export const vehiclesApi = {
  list: (skip = 0, limit = 100, status?: string) =>
    apiClient.get<VehicleListResponse>('/vehicles', {
      params: { skip, limit, status },
    }),

  getById: (id: number) =>
    apiClient.get<Vehicle>(`/vehicles/${id}`),

  create: (data: VehicleCreate) =>
    apiClient.post<Vehicle>('/vehicles', data),

  update: (id: number, data: VehicleUpdate) =>
    apiClient.put<Vehicle>(`/vehicles/${id}`, data),

  delete: (id: number) =>
    apiClient.delete(`/vehicles/${id}`),
};
