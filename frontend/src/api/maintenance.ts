/**
 * API клиент для модуля ТО и Ремонтов
 */
import apiClient from './client';

// === Типы ===

export type MaintenanceOrderType = 'scheduled' | 'repair' | 'diagnostic' | 'inspection';
export type MaintenanceOrderStatus = 'planned' | 'in_progress' | 'completed' | 'cancelled';
export type MaintenancePriority = 'low' | 'medium' | 'high' | 'critical';

export interface MaintenancePart {
  id?: number;
  name: string;
  part_number?: string;
  quantity: number;
  unit_price: number;
  total_price?: number;
  supplier?: string;
  notes?: string;
}

export interface MaintenanceWork {
  id?: number;
  work_type: string;
  description?: string;
  labor_hours: number;
  hourly_rate: number;
  total_cost?: number;
}

export interface MaintenanceOrder {
  id: number;
  order_number: string;
  vehicle_id: number;
  vehicle_name?: string;
  company_id: number;
  order_type: MaintenanceOrderType;
  status: MaintenanceOrderStatus;
  priority: MaintenancePriority;
  title: string;
  description?: string;
  symptoms?: string;
  started_at?: string;
  completed_at?: string;
  planned_completion?: string;
  planned_hours?: number;
  actual_hours?: number;
  parts_cost: number;
  labor_cost: number;
  total_cost: number;
  engine_hours_at_start?: number;
  engine_hours_at_completion?: number;
  assigned_to_id?: number;
  assigned_to_name?: string;
  created_by_id: number;
  created_by_name?: string;
  photos_before?: Record<string, unknown>;
  photos_after?: Record<string, unknown>;
  notes?: string;
  created_at: string;
  updated_at: string;
  parts?: MaintenancePart[];
  works?: MaintenanceWork[];
}

export interface MaintenanceOrderListResponse {
  items: MaintenanceOrder[];
  total: number;
}

export interface UpcomingVehicle {
  vehicle_id: number;
  vehicle_name: string;
  engine_hours: number;
  next_maintenance_hours: number;
  hours_until_to: number;
}

export interface CheckScheduledResponse {
  created_count: number;
  orders: Array<{
    order_id: number;
    order_number: string;
    vehicle_id: number;
    vehicle_name: string;
    engine_hours: number;
    next_maintenance_hours: number;
    hours_overdue: number;
    priority: MaintenancePriority;
  }>;
}

export interface CreateOrderPayload {
  vehicle_id: number;
  order_type: MaintenanceOrderType;
  priority: MaintenancePriority;
  title: string;
  description?: string;
  symptoms?: string;
  planned_hours?: number;
  planned_completion?: string;
  assigned_to_id?: number;
  notes?: string;
  parts: MaintenancePart[];
  works: MaintenanceWork[];
}

export interface CompleteOrderPayload {
  actual_hours?: number;
  engine_hours_at_completion?: number;
  notes?: string;
  photos_after?: Record<string, unknown>;
}

// === API функции (ВАЖНО: без /api/v1, т.к. baseURL уже содержит его) ===

export async function listMaintenanceOrders(params?: {
  skip?: number;
  limit?: number;
  status?: MaintenanceOrderStatus;
  order_type?: MaintenanceOrderType;
  vehicle_id?: number;
  priority?: MaintenancePriority;
}): Promise<MaintenanceOrderListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.skip) searchParams.set('skip', String(params.skip));
  if (params?.limit) searchParams.set('limit', String(params.limit));
  if (params?.status) searchParams.set('status', params.status);
  if (params?.order_type) searchParams.set('order_type', params.order_type);
  if (params?.vehicle_id) searchParams.set('vehicle_id', String(params.vehicle_id));
  if (params?.priority) searchParams.set('priority', params.priority);

  const query = searchParams.toString();
  const url = `/maintenance/orders${query ? `?${query}` : ''}`;
  const response = await apiClient.get(url);
  return response.data;
}

export async function getMaintenanceOrder(orderId: number): Promise<MaintenanceOrder> {
  const response = await apiClient.get(`/maintenance/orders/${orderId}`);
  return response.data;
}

export async function createMaintenanceOrder(
  payload: CreateOrderPayload
): Promise<MaintenanceOrder> {
  const response = await apiClient.post('/maintenance/orders', payload);
  return response.data;
}

export async function updateMaintenanceOrder(
  orderId: number,
  payload: Partial<CreateOrderPayload>
): Promise<MaintenanceOrder> {
  const response = await apiClient.put(`/maintenance/orders/${orderId}`, payload);
  return response.data;
}

export async function completeMaintenanceOrder(
  orderId: number,
  payload: CompleteOrderPayload
): Promise<MaintenanceOrder> {
  const response = await apiClient.post(`/maintenance/orders/${orderId}/complete`, payload);
  return response.data;
}

export async function checkScheduledMaintenance(): Promise<CheckScheduledResponse> {
  const response = await apiClient.post('/maintenance/check-scheduled');
  return response.data;
}

export async function getUpcomingMaintenance(
  hoursThreshold: number = 50
): Promise<{ threshold_hours: number; vehicles_count: number; vehicles: UpcomingVehicle[] }> {
  const response = await apiClient.get(
    `/maintenance/upcoming?hours_threshold=${hoursThreshold}`
  );
  return response.data;
}
