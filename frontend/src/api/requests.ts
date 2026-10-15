import apiClient from './client';

export interface StatusLogEntry {
  id: number;
  from_status: string | null;
  to_status: string;
  changed_by_email: string;
  comment: string | null;
  changed_at: string | null;
}

export type RequestStatus =
  | 'new'
  | 'processing'
  | 'assigned'
  | 'confirmed'
  | 'released'
  | 'in_progress'
  | 'completed'
  | 'signed'
  | 'closed'
  | 'cancelled'
  | 'disputed';

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
  // 🆕 Enrichment поля
  client_name?: string | null;
  vehicle_category_name?: string | null;
  assigned_vehicle_name?: string | null;
  assigned_operator_name?: string | null;
}

export interface RequestCreate {
  client_id?: number;
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
  async getAll(params?: {
    status?: string;
    priority?: string;
    client_id?: number;
    vehicle_category_id?: number;
    assigned_vehicle_id?: number;
    work_type?: string;
    search?: string;
    date_from?: string;
    date_to?: string;
    sort_by?: string;
    sort_order?: 'asc' | 'desc';
    limit?: number;
    offset?: number;
  }): Promise<Request[]> {
    const response = await apiClient.get<Request[]>('/requests', { params });
    return response.data;
  },

  async getById(id: number): Promise<Request> {
    const response = await apiClient.get<Request>(`/requests/${id}`);
    return response.data;
  },

  async create(data: RequestCreate): Promise<Request> {
    const payload: any = {
      client_id: data.client_id,
      request_type: data.request_type,
      work_type: data.work_type,
      object_address: data.object_address,
      planned_start: new Date(data.planned_start).toISOString(),
      planned_end: new Date(data.planned_end).toISOString(),
      rate_type: data.rate_type,
      source_channel: data.source_channel,
      priority: data.priority,
    };

    if (data.shift_duration_hours !== undefined && data.shift_duration_hours !== null) {
      payload.shift_duration_hours = parseFloat(String(data.shift_duration_hours));
    }
    if (data.client_rate !== undefined && data.client_rate !== null) {
      payload.client_rate = parseFloat(String(data.client_rate));
    }
    if (data.estimated_amount !== undefined && data.estimated_amount !== null) {
      payload.estimated_amount = parseFloat(String(data.estimated_amount));
    }
    if (data.vehicle_category_id !== undefined && data.vehicle_category_id !== null) {
      payload.vehicle_category_id = data.vehicle_category_id;
    }
    if (data.comment) payload.comment = data.comment;

    console.log('📤 Creating request:', payload);
    const response = await apiClient.post<Request>('/requests', payload);
    return response.data;
  },

  async update(id: number, data: RequestUpdate): Promise<Request> {
    const response = await apiClient.patch<Request>(`/requests/${id}`, data);
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

  async getHistory(id: number): Promise<StatusLogEntry[]> {
    const response = await apiClient.get<StatusLogEntry[]>(`/requests/${id}/history`);
    return response.data;
  },
  async exportPdf(params?: Record<string, any>): Promise<Blob> {
    const response = await apiClient.get('/requests/export/pdf', { params, responseType: 'blob' });
    return response.data;
  },

  async exportExcel(params?: Record<string, any>): Promise<Blob> {
    const response = await apiClient.get('/requests/export/excel', { params, responseType: 'blob' });
    return response.data;
  },

};
