"use client";
import { useEffect } from "react";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

interface Vehicle { id: number; name: string; status: string; category_id?: number; last_lat?: number; last_lon?: number; last_speed?: number; last_updated?: string; }
interface Props { vehicles: Vehicle[]; selectedVehicleId: number | null; onSelectVehicle: (id: number) => void; }

function getIcon(status: string, speed?: number) {
  const color = speed && speed > 5 ? "#10b981" : status === "busy" ? "#f59e0b" : status === "free" ? "#3b82f6" : "#6b7280";
  return L.divIcon({
    className: "custom-marker",
    html: '<div style="background:' + color + ';width:24px;height:24px;border-radius:50%;border:3px solid white;box-shadow:0 2px 8px rgba(0,0,0,0.3);"></div>',
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  });
}

function FitBounds({ vehicles }: { vehicles: Vehicle[] }) {
  const map = useMap();
  useEffect(() => {
    const withCoords = vehicles.filter((v) => v.last_lat && v.last_lon);
    if (withCoords.length > 0) {
      const bounds = L.latLngBounds(withCoords.map((v) => [v.last_lat!, v.last_lon!] as [number, number]));
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 14 });
    }
  }, [vehicles, map]);
  return null;
}

export default function TelematicsMap({ vehicles, selectedVehicleId, onSelectVehicle }: Props) {
  const vehiclesWithCoords = vehicles.filter((v) => v.last_lat && v.last_lon);
  const defaultCenter: [number, number] = [55.7558, 37.6173];
  return (
    <MapContainer center={defaultCenter} zoom={10} style={{ height: "100%", width: "100%" }} scrollWheelZoom={true}>
      <TileLayer attribution="OpenStreetMap" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      {vehiclesWithCoords.length > 0 && <FitBounds vehicles={vehiclesWithCoords} />}
      {vehiclesWithCoords.map((v) => (
        <Marker key={v.id} position={[v.last_lat!, v.last_lon!]} icon={getIcon(v.status, v.last_speed)} eventHandlers={{ click: () => onSelectVehicle(v.id) }}>
          <Popup>
            <div className="text-sm">
              <div className="font-bold">{v.name}</div>
              <div>Скорость: {v.last_speed?.toFixed(1) || 0} км/ч</div>
              <div>Статус: {v.status}</div>
            </div>
          </Popup>
          <Popup>
            <div className="text-sm">
              <div className="font-bold">{v.name}</div>
              <div className="text-slate-600">#{v.category_id || "-"}</div>
              <div className="mt-2">Status: <b>{v.status}</b></div>
              {v.last_speed !== undefined && <div>Speed: <b>{v.last_speed.toFixed(1)} km/h</b></div>}
            </div>
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}
