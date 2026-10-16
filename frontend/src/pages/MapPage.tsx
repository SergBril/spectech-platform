import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet.markercluster/dist/MarkerCluster.css';
import 'leaflet.markercluster/dist/MarkerCluster.Default.css';
import 'leaflet.markercluster';
import 'leaflet-draw/dist/leaflet.draw.css';
import 'leaflet-draw';
import Layout from '../components/Layout';
import { showToast } from '../utils/toast';
import { mapApi, VehiclePosition, TrackPoint } from '../api/map';
import apiClient from '../api/client';
import { useWebSocket } from '../contexts/WebSocketContext';

// Исправляем иконки Leaflet
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

const formatSpeed = (speed?: number) => speed != null ? `${Math.round(speed)} км/ч` : '—';
const formatDate = (iso?: string) => iso ? new Date(iso).toLocaleString('ru-RU') : '—';

export const MapPage: React.FC = () => {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstance = useRef<L.Map | null>(null);
  const clusterRef = useRef<L.MarkerClusterGroup | null>(null);
  const polylineRef = useRef<L.Polyline | null>(null);

  const [positions, setPositions] = useState<VehiclePosition[]>([]);
  const [selectedVehicle, setSelectedVehicle] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [trackLoading, setTrackLoading] = useState(false);

  // WebSocket real-time positions
  const { subscribe, connected } = useWebSocket();

  // Фильтры
  const [filterEngine, setFilterEngine] = useState<'all' | 'on' | 'off'>('all');
  const [filterSearch, setFilterSearch] = useState('');

  // WebSocket subscription for real-time GPS updates
  useEffect(() => {
    const unsubscribe = subscribe('gps_positions', (data: any) => {
      if (data.positions && Array.isArray(data.positions)) {
        setPositions(data.positions);
      }
    });
    return unsubscribe;
  }, [subscribe]);

  // Автообновление
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState(30);
  const refreshTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const wsConnectedRef = useRef(false);
  const isAutoRefreshRef = useRef(false);

  useEffect(() => { wsConnectedRef.current = connected; }, [connected]);

  // Период для маршрута
  const now = new Date();
  const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000);
  const [trackDateFrom, setTrackDateFrom] = useState(yesterday.toISOString().split('T')[0]);
  const [trackDateTo, setTrackDateTo] = useState(now.toISOString().split('T')[0]);

  // Геозоны
  const [geofences, setGeofences] = useState<any[]>([]);
  const [drawMode, setDrawMode] = useState(false);
  const [editingGeofence, setEditingGeofence] = useState<any>(null);
  const [geofenceName, setGeofenceName] = useState('');
  const [geofenceType, setGeofenceType] = useState<'circle' | 'polygon'>('circle');
  const drawnItemsRef = useRef<L.FeatureGroup | null>(null);
  const geofenceLayersRef = useRef<Map<number, L.Layer>>(new Map());

  // Инициализация карты
  useEffect(() => {
    if (!mapRef.current || mapInstance.current) return;

    const map = L.map(mapRef.current).setView([55.7558, 37.6173], 10);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 19,
    }).addTo(map);

    const cluster = L.markerClusterGroup({
      maxClusterRadius: 50,
      spiderfyOnMaxZoom: true,
      showCoverageOnHover: false,
    });
    map.addLayer(cluster);

    const drawnItems = new L.FeatureGroup();
    map.addLayer(drawnItems);
    drawnItemsRef.current = drawnItems;

    const drawControl = new L.Control.Draw({
      position: 'topright',
      draw: {
        polyline: false,
        rectangle: false,
        marker: false,
        circlemarker: false,
        circle: { shapeOptions: { color: '#f59e0b', fillColor: '#f59e0b', fillOpacity: 0.15 } },
        polygon: { shapeOptions: { color: '#8b5cf6', fillColor: '#8b5cf6', fillOpacity: 0.15 } },
      },
      edit: { featureGroup: drawnItems, remove: false },
    });
    map.addControl(drawControl);

    map.on(L.Draw.Event.CREATED, async (e: any) => {
      const { layerType, layer } = e;
      drawnItems.clearLayers();

      let geoData: Record<string, any> = {};
      if (layerType === 'circle') {
        const center = layer.getLatLng();
        geoData = {
          type: 'circle',
          center_latitude: center.lat,
          center_longitude: center.lng,
          radius_meters: layer.getRadius(),
        };
      } else if (layerType === 'polygon') {
        const latlngs = layer.getLatLngs()[0].map((ll: L.LatLng) => [ll.lat, ll.lng]);
        geoData = { type: 'polygon', polygon: latlngs };
      }

      const name = prompt('Название геозоны:', 'Новая геозона');
      if (!name) return;

      try {
        await mapApi.createGeofence({ name, ...geoData });
        showToast.success('✅ Геозона создана');
        loadGeofences();
      } catch (err: any) {
        showToast.error('Ошибка: ' + (err?.response?.data?.detail || err.message));
      }
    });

    mapInstance.current = map;
    clusterRef.current = cluster;

    return () => {
      map.remove();
      mapInstance.current = null;
      clusterRef.current = null;
    };
  }, []);

  // Загрузка позиций
  useEffect(() => {
    loadPositions();
  }, []);

  // Автообновление позиций
  useEffect(() => {
    if (autoRefresh && refreshInterval > 0) {
      refreshTimerRef.current = setInterval(() => {
        isAutoRefreshRef.current = true;
        loadPositions();
      }, refreshInterval * 1000);
    }

    return () => {
      if (refreshTimerRef.current) {
        clearInterval(refreshTimerRef.current);
        refreshTimerRef.current = null;
      }
    };
  }, [autoRefresh, refreshInterval]);

  // Загрузка геозон
  useEffect(() => {
    loadGeofences();
  }, []);

  // Рендеринг геозон на карте
  useEffect(() => {
    if (!mapInstance.current) return;

    geofenceLayersRef.current.forEach((layer) => layer.remove());
    geofenceLayersRef.current.clear();

    geofences.forEach((gf) => {
      let layer: L.Layer | null = null;

      if (gf.type === 'circle' && gf.center_latitude && gf.center_longitude && gf.radius_meters) {
        layer = L.circle([gf.center_latitude, gf.center_longitude], {
          radius: gf.radius_meters,
          color: '#f59e0b',
          fillColor: '#f59e0b',
          fillOpacity: 0.15,
          weight: 2,
        }).bindTooltip(gf.name, { permanent: false });
      } else if (gf.type === 'polygon' && gf.polygon && gf.polygon.length > 2) {
        const latlngs = gf.polygon.map((p: any) => [p[0], p[1]] as [number, number]);
        layer = L.polygon(latlngs, {
          color: '#8b5cf6',
          fillColor: '#8b5cf6',
          fillOpacity: 0.15,
          weight: 2,
        }).bindTooltip(gf.name, { permanent: false });
      }

      if (layer) {
        layer.addTo(mapInstance.current!);
        layer.on('click', () => {
          setEditingGeofence(gf);
          setGeofenceName(gf.name);
          setGeofenceType(gf.type || 'circle');
        });
        geofenceLayersRef.current.set(gf.id, layer);
      }
    });
  }, [geofences]);

  // Обновление маркеров при изменении позиций или фильтров
  useEffect(() => {
    if (!mapInstance.current || !clusterRef.current) return;

    clusterRef.current.clearLayers();

    const filtered = positions.filter((pos) => {
      if (filterEngine === 'on' && pos.engine_on !== true) return false;
      if (filterEngine === 'off' && pos.engine_on === true) return false;
      if (filterSearch) {
        const search = filterSearch.toLowerCase();
        const name = (pos.vehicle_name || '').toLowerCase();
        if (!name.includes(search)) return false;
      }
      return true;
    });

    if (filtered.length === 0) return;

    const bounds = L.latLngBounds([]);

    filtered.forEach((pos) => {
      const isSelected = selectedVehicle === pos.vehicle_id;
      const color = isSelected ? '#dc2626' : pos.engine_on ? '#16a34a' : '#6b7280';
      const size = isSelected ? 20 : 14;

      const icon = L.divIcon({
        className: 'custom-marker',
        html: `<div style="
          background: ${color};
          width: ${size}px; height: ${size}px;
          border-radius: 50%;
          border: 3px solid white;
          box-shadow: 0 2px 6px rgba(0,0,0,0.3);
          transition: all 0.2s;
        "></div>`,
        iconSize: [size, size],
        iconAnchor: [size / 2, size / 2],
      });

      const marker = L.marker([pos.latitude, pos.longitude], { icon })
        .bindPopup(`
          <div style="min-width: 200px;">
            <strong>${pos.vehicle_name}</strong><br/>
            📍 ${pos.latitude.toFixed(5)}, ${pos.longitude.toFixed(5)}<br/>
            🏎️ ${formatSpeed(pos.speed)}<br/>
            ⛽ Топливо: ${pos.fuel_level != null ? `${Math.round(pos.fuel_level)}%` : '—'}<br/>
            🔧 Двигатель: ${pos.engine_on ? '✅ Вкл' : '❌ Выкл'}<br/>
            🕐 ${formatDate(pos.recorded_at)}
          </div>
        `);

      marker.on('click', () => {
        setSelectedVehicle(pos.vehicle_id);
        loadTrack(pos.vehicle_id);
      });

      clusterRef.current!.addLayer(marker);
      bounds.extend([pos.latitude, pos.longitude]);
    });

    // Центрируем карту только при первой загрузке или ручном обновлении (не при автообновлении)
    if (!selectedVehicle && filtered.length > 0 && bounds.isValid() && !isAutoRefreshRef.current) {
      mapInstance.current.fitBounds(bounds, { padding: [50, 50] });
    }

    // Сбрасываем флаг автообновления после рендера
    isAutoRefreshRef.current = false;
  }, [positions, selectedVehicle, filterEngine, filterSearch]);

  const loadPositions = async () => {
    try {
      setLoading(true);
      // Основной источник: /gps/positions/latest (всегда содержит last known fuel_level)
      try {
        const gpsPositions = await mapApi.getGpsPositions();
        if (gpsPositions.length > 0) {
          setPositions(gpsPositions);
          return;
        }
      } catch (gpsErr) {
        console.warn('GPS positions endpoint failed, trying map endpoint', gpsErr);
      }

      // Fallback: старый эндпоинт /map/vehicles/positions
      const data = await mapApi.getVehiclePositions();
      if (data.positions && data.positions.length > 0) {
        setPositions(data.positions);
      } else {
        if (!isAutoRefreshRef.current) {
          showToast.info('Нет данных о позициях техники');
        }
      }
    } catch (err: any) {
      if (!isAutoRefreshRef.current) {
        showToast.error('Ошибка загрузки позиций: ' + (err?.response?.data?.detail || err.message));
      }
    } finally {
      setLoading(false);
    }
  };

  const loadGeofences = async () => {
    try {
      const data = await mapApi.getGeofences();
      setGeofences(data.geofences);
    } catch (err) {
      console.error('Failed to load geofences', err);
    }
  };

  const loadTrack = async (vehicleId: number) => {
    try {
      setTrackLoading(true);

      let points: TrackPoint[] = [];

      try {
        const data = await mapApi.getVehicleTrack(
          vehicleId,
          new Date(trackDateFrom).toISOString(),
          new Date(trackDateTo + 'T23:59:59').toISOString()
        );
        points = data.points;
      } catch {
        const res = await apiClient.get('/gps/points', {
          params: {
            vehicle_id: vehicleId,
            date_from: new Date(trackDateFrom).toISOString(),
            date_to: new Date(trackDateTo + 'T23:59:59').toISOString(),
            limit: 1000,
          },
        });
        points = res.data.map((p: any) => ({
          latitude: p.latitude,
          longitude: p.longitude,
          speed: p.speed,
          heading: p.heading,
          recorded_at: p.recorded_at,
        }));
      }

      if (polylineRef.current) {
        polylineRef.current.remove();
        polylineRef.current = null;
      }

      if (points.length > 0 && mapInstance.current) {
        const latlngs = points.map((p: TrackPoint) => [p.latitude, p.longitude] as [number, number]);
        const polyline = L.polyline(latlngs, {
          color: '#3b82f6',
          weight: 3,
          opacity: 0.7,
        }).addTo(mapInstance.current);

        polylineRef.current = polyline;
        mapInstance.current.fitBounds(polyline.getBounds(), { padding: [50, 50] });
        showToast.success(`🛤️ Маршрут: ${points.length} точек`);
      } else {
        showToast.info('Нет данных маршрута за выбранный период');
      }
    } catch (err: any) {
      showToast.error('Ошибка загрузки маршрута: ' + (err?.response?.data?.detail || err.message));
    } finally {
      setTrackLoading(false);
    }
  };

  const clearSelection = () => {
    setSelectedVehicle(null);
    if (polylineRef.current) {
      polylineRef.current.remove();
      polylineRef.current = null;
    }
    if (positions.length > 0 && mapInstance.current) {
      const bounds = L.latLngBounds(positions.map((p) => [p.latitude, p.longitude] as [number, number]));
      if (bounds.isValid()) mapInstance.current.fitBounds(bounds, { padding: [50, 50] });
    }
  };

  const filteredPositions = positions.filter((pos) => {
    if (filterEngine === 'on' && pos.engine_on !== true) return false;
    if (filterEngine === 'off' && pos.engine_on === true) return false;
    if (filterSearch) {
      const search = filterSearch.toLowerCase();
      const name = (pos.vehicle_name || '').toLowerCase();
      if (!name.includes(search)) return false;
    }
    return true;
  });

  return (
    <Layout>
      <div className="flex h-[calc(100vh-64px)]">
        {/* Sidebar */}
        <div className="w-80 bg-white border-r overflow-y-auto flex-shrink-0">
          <div className="p-4 border-b space-y-3">
            <h2 className="text-lg font-bold text-gray-900">🗺️ Карта техники</h2>
            <p className="text-xs text-gray-500">
              {filteredPositions.length} из {positions.length} ед.
            </p>

            {/* Поиск */}
            <input
              type="text"
              placeholder="🔍 Поиск техники..."
              value={filterSearch}
              onChange={(e) => setFilterSearch(e.target.value)}
              className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
            />

            {/* Фильтр двигателя */}
            <div className="flex gap-1">
              {(['all', 'on', 'off'] as const).map((val) => (
                <button
                  key={val}
                  onClick={() => setFilterEngine(val)}
                  className={`flex-1 px-2 py-1 text-xs rounded transition-colors ${
                    filterEngine === val
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {val === 'all' ? 'Все' : val === 'on' ? '🟢 Вкл' : '⚫ Выкл'}
                </button>
              ))}
            </div>

            {/* Кнопки */}
            <div className="flex gap-2">
              <button
                onClick={() => {
                  isAutoRefreshRef.current = false;
                  loadPositions();
                }}
                disabled={loading}
                className="bg-blue-600 text-white px-3 py-1.5 rounded text-sm hover:bg-blue-700 disabled:opacity-50 flex-1"
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

            {/* Автообновление */}
            <div className="flex items-center justify-between pt-2 border-t">
              <label className="flex items-center gap-2 text-xs cursor-pointer">
                <input
                  type="checkbox"
                  checked={autoRefresh}
                  onChange={(e) => setAutoRefresh(e.target.checked)}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span className="text-gray-700 font-medium">Автообновление</span>
              </label>
              {autoRefresh && (
                <select
                  value={refreshInterval}
                  onChange={(e) => setRefreshInterval(Number(e.target.value))}
                  className="border border-gray-300 rounded px-2 py-1 text-xs w-20 focus:ring-2 focus:ring-blue-500 outline-none"
                >
                  <option value={10}>10 сек</option>
                  <option value={30}>30 сек</option>
                  <option value={60}>1 мин</option>
                  <option value={300}>5 мин</option>
                </select>
              )}
            </div>
            {autoRefresh && (
              <div className="flex items-center gap-1.5">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                </span>
                {connected ? (
                <span className="text-[10px] text-blue-600 font-medium">⚡ WebSocket Real-time</span>
              ) : (
                <span className="text-[10px] text-green-600">Live • каждые {refreshInterval}с</span>
              )}
              </div>
            )}

            {/* Период маршрута */}
            {selectedVehicle && (
              <div className="pt-2 border-t space-y-2">
                <p className="text-xs font-medium text-gray-700">📅 Период маршрута:</p>
                <div className="flex gap-2">
                  <input
                    type="date"
                    value={trackDateFrom}
                    onChange={(e) => setTrackDateFrom(e.target.value)}
                    className="flex-1 border border-gray-300 rounded px-2 py-1 text-xs"
                  />
                  <input
                    type="date"
                    value={trackDateTo}
                    onChange={(e) => setTrackDateTo(e.target.value)}
                    className="flex-1 border border-gray-300 rounded px-2 py-1 text-xs"
                  />
                </div>
                <button
                  onClick={() => loadTrack(selectedVehicle)}
                  disabled={trackLoading}
                  className="w-full bg-indigo-600 text-white px-3 py-1.5 rounded text-xs hover:bg-indigo-700 disabled:opacity-50"
                >
                  {trackLoading ? '⏳ Загрузка...' : '🛤️ Показать маршрут'}
                </button>
              </div>
            )}

            {/* Геозоны */}
            <div className="pt-3 border-t space-y-2">
              <div className="flex items-center justify-between">
                <p className="text-xs font-medium text-gray-700">🔲 Геозоны ({geofences.length})</p>
                <button
                  onClick={() => setDrawMode(!drawMode)}
                  className={`text-xs px-2 py-1 rounded transition-colors ${
                    drawMode ? 'bg-amber-500 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {drawMode ? '✋ Стоп' : '✏️ Рисовать'}
                </button>
              </div>

              {drawMode && (
                <div className="bg-amber-50 rounded p-2 text-xs text-amber-800 border border-amber-200">
                  Используйте инструменты рисования в правом верхнем углу карты
                </div>
              )}

              {editingGeofence && (
                <div className="bg-indigo-50 rounded-lg p-3 space-y-2 border border-indigo-200">
                  <p className="text-xs font-medium text-indigo-900">✏️ Редактирование: {editingGeofence.name}</p>
                  <input
                    type="text"
                    value={geofenceName}
                    onChange={(e) => setGeofenceName(e.target.value)}
                    className="w-full border border-indigo-300 rounded px-2 py-1 text-xs bg-white"
                    placeholder="Название"
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={async () => {
                        try {
                          await mapApi.updateGeofence(editingGeofence.id, { name: geofenceName });
                          showToast.success('✅ Геозона обновлена');
                          setEditingGeofence(null);
                          loadGeofences();
                        } catch (err: any) {
                          showToast.error('Ошибка обновления');
                        }
                      }}
                      className="flex-1 bg-indigo-600 text-white px-2 py-1 rounded text-xs hover:bg-indigo-700"
                    >
                      💾 Сохранить
                    </button>
                    <button
                      onClick={async () => {
                        if (!confirm(`Удалить геозону "${editingGeofence.name}"?`)) return;
                        try {
                          await mapApi.deleteGeofence(editingGeofence.id);
                          showToast.success('🗑️ Геозона удалена');
                          setEditingGeofence(null);
                          loadGeofences();
                        } catch (err: any) {
                          showToast.error('Ошибка удаления');
                        }
                      }}
                      className="bg-red-500 text-white px-2 py-1 rounded text-xs hover:bg-red-600"
                    >
                      🗑️
                    </button>
                    <button
                      onClick={() => setEditingGeofence(null)}
                      className="bg-white text-gray-600 px-2 py-1 rounded text-xs border border-gray-300 hover:bg-gray-100"
                    >
                      ✕
                    </button>
                  </div>
                </div>
              )}

              <div className="max-h-32 overflow-y-auto divide-y">
                {geofences.map((gf) => (
                  <div
                    key={gf.id}
                    onClick={() => {
                      setEditingGeofence(gf);
                      setGeofenceName(gf.name);
                      setGeofenceType(gf.type || 'circle');
                    }}
                    className={`py-1.5 px-2 cursor-pointer hover:bg-gray-50 text-xs rounded ${
                      editingGeofence?.id === gf.id ? 'bg-indigo-50 text-indigo-900' : 'text-gray-700'
                    }`}
                  >
                    <span className="mr-1">{gf.type === 'circle' ? '⭕' : '🔷'}</span>
                    {gf.name}
                  </div>
                ))}
                {geofences.length === 0 && (
                  <div className="text-xs text-gray-400 text-center py-2">Нет геозон</div>
                )}
              </div>
            </div>
          </div>

          {/* Список техники */}
          <div className="divide-y">
            {filteredPositions.length === 0 && !loading && (
              <div className="p-4 text-center text-gray-500 text-sm">
                Нет техники по выбранным фильтрам.
              </div>
            )}
            {filteredPositions.map((pos) => (
              <div
                key={pos.vehicle_id}
                onClick={() => {
                  setSelectedVehicle(pos.vehicle_id);
                  loadTrack(pos.vehicle_id);
                }}
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
                  <span>⛽ {pos.fuel_level != null ? `${Math.round(pos.fuel_level)}%` : '—'}</span>
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