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
};