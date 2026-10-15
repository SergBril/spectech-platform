import apiClient from './client';

export type VehicleStatus = 'free' | 'busy' | 'maintenance';
export type IdType = 'license_plate' | 'VIN' | 'inventory' | 'chassis' | 'body' | 'custom';

export interface AttributeValue {
  slug: string;
  name: string;
  data_type: 'select' | 'number' | 'text' | 'boolean';
  unit: string | null;
  value_text: string | null;
  value_number: number | null;
  value_boolean: boolean | null;
}

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
  // 🆕 Новые поля каталога
  subcategory_id?: number | null;
  make?: string | null;
  model?: string | null;
  vin?: string | null;
  attribute_values?: AttributeValue[];
  category_name?: string | null;
  subcategory_name?: string | null;
  assigned_driver_id?: number | null;
  assigned_driver_name?: string | null;
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
  subcategory_id?: number;
  make?: string;
  model?: string;
  vin?: string;
  owner_id?: number;
  is_custom_number?: boolean;
  attributes?: Record<string, any>;
}

export interface VehicleUpdate extends Partial<VehicleCreate> {
  assigned_driver_id?: number | null;
}

export interface VehicleListResponse {
  items: Vehicle[];
  total: number;
}

export const vehiclesApi = {
  async list(params?: {
    status?: VehicleStatus;
    limit?: number;
    skip?: number;
  }): Promise<{ items: Vehicle[]; total: number }> {
    const response = await apiClient.get<VehicleListResponse>('/vehicles', { params });
    return response.data;
  },

  async getAll(params?: {
    status?: VehicleStatus;
    limit?: number;
    skip?: number;
  }): Promise<Vehicle[]> {
    const result = await this.list(params);
    return result.items;
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
    const response = await apiClient.put<Vehicle>(`/vehicles/${id}`, data);
    return response.data;
  },

  async delete(id: number): Promise<void> {
    await apiClient.delete(`/vehicles/${id}`);
  },
};
