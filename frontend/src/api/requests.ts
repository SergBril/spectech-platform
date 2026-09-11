import apiClient from './client';

export type RequestStatus = 'draft' | 'pending' | 'approved' | 'in_progress' | 'completed' | 'cancelled';
export type RequestType = 'one_time' | 'recurring';
export type RateType = 'hourly' | 'daily' | 'shift' | 'fixed';
export type SourceChannel = 'phone' | 'web' | 'mobile' | 'email';
export type Priority = 'low' | 'normal' | 'high' | 'urgent';

export interface Request {
  id: number;
  client_id: number | null;
  status: RequestStatus;
  request_type: RequestType;
  vehicle_category_id: number | null;
  work_type: string;
  object_address: string;
  planned_start: string;
  planned_end: string;
  actual_start: string | null;
  actual_end: string | null;
  shift_duration_hours: number | string | null;
  client_rate: number | string | null;
  rate_type: RateType | string;
  estimated_amount: number | string | null;
  final_amount: number | string | null;
  assigned_vehicle_id: number | null;
  assigned_operator_id: number | null;
  source_channel: SourceChannel | string;
  priority: Priority | string;
  comment: string | null;
  created_at: string;
}

export interface RequestCreate {
  client_id?: number | null;
  request_type: RequestType;
  vehicle_category_id?: number | null;
  work_type: string;
  object_address: string;
  planned_start: string;
  planned_end: string;
  shift_duration_hours?: number;
  client_rate?: number;
  rate_type: RateType;
  estimated_amount?: number;
  source_channel: SourceChannel;
  priority: Priority;
  comment?: string;
}

export interface RequestUpdate extends Partial<RequestCreate> {
  status?: RequestStatus;
  final_amount?: number;
  assigned_vehicle_id?: number | null;
  assigned_operator_id?: number | null;
}

export const requestsApi = {
  async getAll(params?: { status?: RequestStatus; client_id?: number; limit?: number; offset?: number }): Promise<Request[]> {
    const response = await apiClient.get<Request[]>('/requests', { params });
    return response.data;
  },

  async getById(id: number): Promise<Request> {
    const response = await apiClient.get<Request>(`/requests/${id}`);
    return response.data;
  },

  async create(data: RequestCreate): Promise<Request> {
    const response = await apiClient.post<Request>('/requests', data);
    return response.data;
  },

  async update(id: number, data: RequestUpdate): Promise<Request> {
    const response = await apiClient.put<Request>(`/requests/${id}`, data);
    return response.data;
  },

  async delete(id: number): Promise<void> {
    await apiClient.delete(`/requests/${id}`);
  },

  async assign(id: number, vehicleId: number, operatorId?: number): Promise<Request> {
    const response = await apiClient.post<Request>(`/requests/${id}/assign`, {
      vehicle_id: vehicleId,
      operator_id: operatorId,
    });
    return response.data;
  },
};
