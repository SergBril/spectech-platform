"use client";
import { useEffect } from "react";
import { MapContainer, TileLayer, Polyline, Marker, Popup, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

interface GpsPoint {
  id: number;
  latitude: number;
  longitude: number;
  speed?: number | null;
  recorded_at: string;
}

interface Segment {
  positions: [number, number][];
  color: string;
}

interface Props {
  segments: Segment[];
  points: GpsPoint[];
}

function FitBounds({ points }: { points: GpsPoint[] }) {
  const map = useMap();
  useEffect(() => {
    if (points.length > 0) {
      const bounds = L.latLngBounds(points.map((p) => [p.latitude, p.longitude] as [number, number]));
      map.fitBounds(bounds, { padding: [50, 50] });
    }
  }, [points, map]);
  return null;
}

function createIcon(color: string) {
  return L.divIcon({
    className: "custom-marker",
    html: `<div style="background:${color};width:16px;height:16px;border-radius:50%;border:3px solid white;box-shadow:0 2px 6px rgba(0,0,0,0.3);"></div>`,
    iconSize: [16, 16],
    iconAnchor: [8, 8],
  });
}

export default function TrackMap({ segments, points }: Props) {
  if (points.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-slate-500">
        Нет данных для отображения
      </div>
    );
  }

  const defaultCenter: [number, number] = [points[0].latitude, points[0].longitude];
  const first = points[0];
  const last = points[points.length - 1];

  return (
    <MapContainer center={defaultCenter} zoom={12} style={{ height: "100%", width: "100%" }} scrollWheelZoom={true}>
      <TileLayer attribution="OpenStreetMap" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      <FitBounds points={points} />
      {segments.map((seg, i) => (
        <Polyline
          key={i}
          positions={seg.positions}
          color={seg.color}
          weight={4}
          opacity={0.8}
        />
      ))}
      <Marker position={[first.latitude, first.longitude]} icon={createIcon("#10b981")}>
        <Popup>
          <div className="text-sm">
            <div className="font-bold">🟢 Старт</div>
            <div>{new Date(first.recorded_at).toLocaleString("ru-RU")}</div>
            {first.speed != null && <div>Скорость: {first.speed.toFixed(1)} км/ч</div>}
          </div>
        </Popup>
      </Marker>
      {points.length > 1 && (
        <Marker position={[last.latitude, last.longitude]} icon={createIcon("#ef4444")}>
          <Popup>
            <div className="text-sm">
              <div className="font-bold">🔴 Конец</div>
              <div>{new Date(last.recorded_at).toLocaleString("ru-RU")}</div>
              {last.speed != null && <div>Скорость: {last.speed.toFixed(1)} км/ч</div>}
            </div>
          </Popup>
        </Marker>
      )}
    </MapContainer>
  );
}
