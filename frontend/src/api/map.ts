import apiClient from './client';

export interface VehiclePosition {
  vehicle_id: number;
  vehicle_name: string;
  vehicle_type?: string;
  status?: string;
  latitude: number;
  longitude: number;
  speed?: number;
  heading?: number;
  engine_on?: boolean;
  fuel_level?: number;
  altitude?: number;
  recorded_at?: string;
}

export interface TrackPoint {
  latitude: number;
  longitude: number;
  speed?: number;
  heading?: number;
  engine_on?: boolean;
  fuel_level?: number;
  recorded_at?: string;
}

export const mapApi = {
  getVehiclePositions: async (): Promise<{ positions: VehiclePosition[] }> => {
    const res = await apiClient.get('/map/vehicles/positions');
    return res.data;
  },

  getGpsPositions: async (): Promise<VehiclePosition[]> => {
    const res = await apiClient.get('/gps/points', { params: { limit: 100 } });
    const points: any[] = res.data;

    // Группируем по vehicle_id, берём последнюю точку
    const latestByVehicle = new Map<number, any>();
    for (const p of points) {
      const existing = latestByVehicle.get(p.vehicle_id);
      if (!existing || new Date(p.recorded_at) > new Date(existing.recorded_at)) {
        latestByVehicle.set(p.vehicle_id, p);
      }
    }

    return Array.from(latestByVehicle.values()).map((p) => ({
      vehicle_id: p.vehicle_id,
      vehicle_name: p.vehicle_name || `Vehicle #${p.vehicle_id}`,
      latitude: p.latitude,
      longitude: p.longitude,
      speed: p.speed != null ? Number(p.speed) : undefined,
      heading: p.heading != null ? Number(p.heading) : undefined,
      engine_on: p.engine_on === true || p.engine_on === 'True' || p.engine_on === 'true',
      fuel_level: p.fuel_level != null && p.fuel_level !== '' ? Number(p.fuel_level) : undefined,
      recorded_at: p.recorded_at,
    }));
  },

  getVehicleTrack: async (
    vehicleId: number,
    dateFrom: string,
    dateTo: string,
    limit = 1000
  ): Promise<{ vehicle_id: number; vehicle_name: string; points: TrackPoint[] }> => {
    const res = await apiClient.get(`/map/vehicles/${vehicleId}/track`, {
      params: { date_from: dateFrom, date_to: dateTo, limit },
    });
    return res.data;
  },

  getGeofences: async (): Promise<{ geofences: any[] }> => {
    const res = await apiClient.get('/map/geofences');
    return res.data;
  },

  getGpsProviders: async (): Promise<{ providers: GpsProviderOption[] }> => {
    const res = await apiClient.get('/map/providers');
    return res.data;
  },

  testGpsProvider: async (
    provider: string,
    config: Record<string, any>
  ): Promise<{ success: boolean; provider: string; error?: string }> => {
    const res = await apiClient.post(`/map/providers/test?provider=${provider}`, config);
    return res.data;
  },

  createGeofence: async (data: Record<string, any>): Promise<{ id: number; message: string }> => {
    const res = await apiClient.post('/map/geofences', data);
    return res.data;
  },

  updateGeofence: async (id: number, data: Record<string, any>): Promise<{ id: number; message: string }> => {
    const res = await apiClient.put(`/map/geofences/${id}`, data);
    return res.data;
  },

  deleteGeofence: async (id: number): Promise<{ message: string }> => {
    const res = await apiClient.delete(`/map/geofences/${id}`);
    return res.data;
  },
};

export interface GpsProviderOption {
  value: string;
  label: string;
}