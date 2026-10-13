import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import Layout from '../components/Layout';
import { showToast } from '../utils/toast';
import { mapApi, VehiclePosition, TrackPoint } from '../api/map';

// Исправляем иконки Leaflet (проблема с webpack/vite)
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

const formatSpeed = (speed?: number) => {
  if (speed == null) return '—';
  return `${Math.round(speed)} км/ч`;
};

const formatDate = (iso?: string) => {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('ru-RU');
};

export const MapPage: React.FC = () => {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstance = useRef<L.Map | null>(null);
  const markersRef = useRef<L.Marker[]>([]);
  const polylineRef = useRef<L.Polyline | null>(null);

  const [positions, setPositions] = useState<VehiclePosition[]>([]);
  const [selectedVehicle, setSelectedVehicle] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [trackLoading, setTrackLoading] = useState(false);

  // Инициализация карты
  useEffect(() => {
    if (!mapRef.current || mapInstance.current) return;

    const map = L.map(mapRef.current).setView([55.7558, 37.6173], 10); // Москва по умолчанию
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 19,
    }).addTo(map);

    mapInstance.current = map;

    return () => {
      map.remove();
      mapInstance.current = null;
    };
  }, []);

  // Загрузка позиций
  useEffect(() => {
    loadPositions();
  }, []);

  // Обновление маркеров при изменении позиций
  useEffect(() => {
    if (!mapInstance.current) return;

    // Удаляем старые маркеры
    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];

    if (positions.length === 0) return;

    const bounds: L.LatLngBounds = L.latLngBounds([]);

    positions.forEach((pos) => {
      const isSelected = selectedVehicle === pos.vehicle_id;
      const color = isSelected ? '#dc2626' : pos.engine_on ? '#16a34a' : '#6b7280';

      const icon = L.divIcon({
        className: 'custom-marker',
        html: `<div style="
          background: ${color};
          width: ${isSelected ? 20 : 14}px;
          height: ${isSelected ? 20 : 14}px;
          border-radius: 50%;
          border: 3px solid white;
          box-shadow: 0 2px 6px rgba(0,0,0,0.3);
          transition: all 0.2s;
        "></div>`,
        iconSize: [isSelected ? 20 : 14, isSelected ? 20 : 14],
        iconAnchor: [isSelected ? 10 : 7, isSelected ? 10 : 7],
      });

      const marker = L.marker([pos.latitude, pos.longitude], { icon })
        .addTo(mapInstance.current!)
        .bindPopup(`
          <div style="min-width: 180px;">
            <strong>${pos.vehicle_name}</strong><br/>
            📍 ${pos.latitude.toFixed(5)}, ${pos.longitude.toFixed(5)}<br/>
            🏎️ ${formatSpeed(pos.speed)}<br/>
            ⛽ Топливо: ${pos.fuel_level != null ? `${pos.fuel_level}%` : '—'}<br/>
            🔧 Двигатель: ${pos.engine_on ? '✅ Вкл' : '❌ Выкл'}<br/>
            🕐 ${formatDate(pos.recorded_at)}
          </div>
        `);

      marker.on('click', () => {
        setSelectedVehicle(pos.vehicle_id);
      });

      markersRef.current.push(marker);
      bounds.extend([pos.latitude, pos.longitude]);
    });

    // Центрируем карту на всех маркерах (только если нет выбранного)
    if (!selectedVehicle && positions.length > 0 && bounds.isValid()) {
      mapInstance.current.fitBounds(bounds, { padding: [50, 50] });
    }
  }, [positions, selectedVehicle]);

  const loadPositions = async () => {
    try {
      setLoading(true);
      const data = await mapApi.getVehiclePositions();
      setPositions(data.positions);
      if (data.positions.length === 0) {
        showToast.info('Нет данных о позициях техники');
      }
    } catch (err: any) {
      showToast.error('Ошибка загрузки позиций: ' + (err?.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const loadTrack = async (vehicleId: number) => {
    try {
      setTrackLoading(true);

      // Маршрут за последние 24 часа
      const now = new Date();
      const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000);

      const data = await mapApi.getVehicleTrack(
        vehicleId,
        yesterday.toISOString(),
        now.toISOString()
      );

      // Удаляем старый маршрут
      if (polylineRef.current) {
        polylineRef.current.remove();
        polylineRef.current = null;
      }

      if (data.points.length > 0 && mapInstance.current) {
        const latlngs = data.points.map((p: TrackPoint) => [p.latitude, p.longitude] as [number, number]);
        const polyline = L.polyline(latlngs, {
          color: '#3b82f6',
          weight: 3,
          opacity: 0.7,
        }).addTo(mapInstance.current);

        polylineRef.current = polyline;
        mapInstance.current.fitBounds(polyline.getBounds(), { padding: [50, 50] });

        showToast.success(`🛤️ Маршрут: ${data.points.length} точек за 24ч`);
      } else {
        showToast.info('Нет данных маршрута за последние 24 часа');
      }
    } catch (err: any) {
      showToast.error('Ошибка загрузки маршрута: ' + (err?.response?.data?.detail || err.message));
    } finally {
      setTrackLoading(false);
    }
  };

  const handleVehicleClick = (vehicleId: number) => {
    setSelectedVehicle(vehicleId);
    loadTrack(vehicleId);
  };

  const clearSelection = () => {
    setSelectedVehicle(null);
    if (polylineRef.current) {
      polylineRef.current.remove();
      polylineRef.current = null;
    }
    // Сброс вида на все маркеры
    if (positions.length > 0 && mapInstance.current) {
      const bounds = L.latLngBounds(positions.map((p) => [p.latitude, p.longitude] as [number, number]));
      if (bounds.isValid()) {
        mapInstance.current.fitBounds(bounds, { padding: [50, 50] });
      }
    }
  };

  return (
    <Layout>
      <div className="flex h-[calc(100vh-64px)]">
        {/* Sidebar */}
        <div className="w-80 bg-white border-r overflow-y-auto flex-shrink-0">
          <div className="p-4 border-b">
            <h2 className="text-lg font-bold text-gray-900">🗺️ Карта техники</h2>
            <p className="text-xs text-gray-500 mt-1">{positions.length} ед. на карте</p>
            <div className="flex gap-2 mt-3">
              <button
                onClick={loadPositions}
                disabled={loading}
                className="bg-blue-600 text-white px-3 py-1.5 rounded text-sm hover:bg-blue-700 disabled:opacity-50"
              >
                {loading ? '⏳' : '🔄 Обновить'}
              </button>
              {selectedVehicle && (
                <button
                  onClick={clearSelection}
                  className="bg-gray-200 text-gray-700 px-3 py-1.5 rounded text-sm hover:bg-gray-300"
                >
                  ✕ Сброс
                </button>
              )}
            </div>
          </div>

          <div className="divide-y">
            {positions.length === 0 && !loading && (
              <div className="p-4 text-center text-gray-500 text-sm">
                Нет данных о позициях.<br/>Проверьте GPS-трекеры.
              </div>
            )}
            {positions.map((pos) => (
              <div
                key={pos.vehicle_id}
                onClick={() => handleVehicleClick(pos.vehicle_id)}
                className={`p-3 cursor-pointer hover:bg-gray-50 transition-colors ${
                  selectedVehicle === pos.vehicle_id ? 'bg-blue-50 border-l-4 border-blue-600' : ''
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium text-sm text-gray-900">{pos.vehicle_name}</span>
                  <span className={`w-2 h-2 rounded-full ${pos.engine_on ? 'bg-green-500' : 'bg-gray-400'}`} />
                </div>
                <div className="text-xs text-gray-500 mt-1 flex gap-3">
                  <span>🏎️ {formatSpeed(pos.speed)}</span>
                  <span>⛽ {pos.fuel_level != null ? `${pos.fuel_level}%` : '—'}</span>
                </div>
                <div className="text-xs text-gray-400 mt-1">{formatDate(pos.recorded_at)}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Map */}
        <div className="flex-1 relative">
          <div ref={mapRef} className="w-full h-full" />
          {trackLoading && (
            <div className="absolute top-4 right-4 bg-white/90 backdrop-blur px-4 py-2 rounded-lg shadow text-sm">
              ⏳ Загрузка маршрута...
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
};

export default MapPage;