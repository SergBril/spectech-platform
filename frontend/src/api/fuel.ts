import apiClient from './client';

export interface FuelAnalytics {
  period: { from: string; to: string };
  total_refuels: number;
  total_drains: number;
  total_volume_refuel: number;
  total_volume_drain: number;
  net_volume: number;
  total_cost: number;
  avg_price_per_liter: number;
  avg_volume_per_refuel: number;
  refuels_by_month: Record<string, number>;
}

export interface ConsumptionRate {
  vehicle_id: number;
  vehicle_name: string;
  total_fuel_liters: number;
  engine_hours: number;
  liters_per_hour: number;
  liters_per_100km: number | null;
}

export interface FuelByVehicle {
  vehicle_id: number;
  vehicle_name: string;
  refuels_count: number;
  drains_count: number;
  total_refuel_volume: number;
  total_drain_volume: number;
  net_volume: number;
  total_cost: number;
  avg_cost_per_refuel: number;
}

export async function getFuelAnalytics(
  dateFrom?: string,
  dateTo?: string,
  vehicleId?: number
): Promise<FuelAnalytics> {
  const params = new URLSearchParams();
  if (dateFrom) params.set('date_from', dateFrom);
  if (dateTo) params.set('date_to', dateTo);
  if (vehicleId) params.set('vehicle_id', vehicleId.toString());

  const response = await apiClient.get(`/telematics/fuel/analytics?${params}`);
  return response.data;
}

export async function getFuelConsumption(vehicleId?: number): Promise<ConsumptionRate[]> {
  const params = new URLSearchParams();
  if (vehicleId) params.set('vehicle_id', vehicleId.toString());

  const response = await apiClient.get(`/telematics/fuel/analytics/consumption?${params}`);
  return response.data;
}

export async function getFuelByVehicle(
  dateFrom?: string,
  dateTo?: string
): Promise<FuelByVehicle[]> {
  const params = new URLSearchParams();
  if (dateFrom) params.set('date_from', dateFrom);
  if (dateTo) params.set('date_to', dateTo);

  const response = await apiClient.get(`/telematics/fuel/analytics/by-vehicle?${params}`);
  return response.data;
}
