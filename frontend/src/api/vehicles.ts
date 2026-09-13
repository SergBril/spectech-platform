import apiClient from './client';

export type VehicleStatus = 'free' | 'working' | 'maintenance' | 'out_of_service';
export type IdType = 'VIN' | 'chassis' | 'body' | 'custom';

export interface Vehicle {
  id: number;
  id_type: IdType;
  id_value: string;
  name: string;
  year: number | null;
  status: VehicleStatus;
  fuel_norm_per_hour: string | null;
  fuel_norm_per_100km: string | null;
  psm_number: string | null;
  osago_expiry_date: string | null;
  category_id: number | null;
  owner_id: number | null;
  company_id: number | null;
  is_custom_number: boolean;
  created_at: string;
  updated_at: string;
}

export interface VehicleCreate {
  id_type: IdType;
  id_value: string;
  name: string;
  year?: number;
  status?: VehicleStatus;
  fuel_norm_per_hour?: number;
  fuel_norm_per_100km?: number;
  psm_number?: string;
  osago_expiry_date?: string;
  category_id?: number;
  owner_id?: number;
  is_custom_number?: boolean;
}

export interface VehicleUpdate extends Partial<VehicleCreate> {}

export const vehiclesApi = {
  async getAll(params?: {
    status?: VehicleStatus;
    limit?: number;
    skip?: number;
  }): Promise<Vehicle[]> {
    const response = await apiClient.get<Vehicle[] | { items: Vehicle[]; total: number }>('/vehicles', {
      params,
    });
    // API может возвращать либо массив, либо объект с пагинацией
    const data = response.data;
    return Array.isArray(data) ? data : (data as any).items || [];
  },

  async getById(id: number): Promise<Vehicle> {
    const response = await apiClient.get<Vehicle>(`/vehicles/${id}`);
    return response.data;
  },

  async create(data: VehicleCreate): Promise<Vehicle> {
    const response = await apiClient.post<Vehicle>('/vehicles', data);
    return response.data;
  },

  async update(id: number, data: VehicleUpdate): Promise<Vehicle> {
    const response = await apiClient.patch<Vehicle>(`/vehicles/${id}`, data);
    return response.data;
  },

  async delete(id: number): Promise<void> {
    await apiClient.delete(`/vehicles/${id}`);
  },
};
