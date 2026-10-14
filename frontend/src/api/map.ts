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
    const res = await apiClient.get('/gps/points', { params: { limit: 500 } });
    const points: any[] = res.data;

    // Группируем по vehicle_id
    const byVehicle = new Map<number, any[]>();
    for (const p of points) {
      if (!byVehicle.has(p.vehicle_id)) byVehicle.set(p.vehicle_id, []);
      byVehicle.get(p.vehicle_id)!.push(p);
    }

    const result: VehiclePosition[] = [];

    for (const [vehicleId, vehiclePoints] of byVehicle) {
      // Сортируем по дате убывание
      vehiclePoints.sort((a, b) => new Date(b.recorded_at).getTime() - new Date(a.recorded_at).getTime());

      const latest = vehiclePoints[0];

      // Ищем последнее ненулевое значение fuel_level
      let fuelLevel: number | undefined = undefined;
      for (const p of vehiclePoints) {
        if (p.fuel_level != null && p.fuel_level !== '' && !isNaN(Number(p.fuel_level))) {
          fuelLevel = Number(p.fuel_level);
          break;
        }
      }

      result.push({
        vehicle_id: vehicleId,
        vehicle_name: latest.vehicle_name || `Vehicle #${vehicleId}`,
        latitude: latest.latitude,
        longitude: latest.longitude,
        speed: latest.speed != null ? Number(latest.speed) : undefined,
        heading: latest.heading != null ? Number(latest.heading) : undefined,
        engine_on: latest.engine_on === true || latest.engine_on === 'True' || latest.engine_on === 'true',
        fuel_level: fuelLevel,
        recorded_at: latest.recorded_at,
      });
    }

    return result;
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