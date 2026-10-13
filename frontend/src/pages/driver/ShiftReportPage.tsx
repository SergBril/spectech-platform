import React, { useState, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { showToast } from '../../utils/toast';
import apiClient from '../../api/client';

export const ShiftReportPage: React.FC = () => {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [motoHours, setMotoHours] = useState('');
  const [odometer, setOdometer] = useState('');
  const [fuelUsed, setFuelUsed] = useState('');
  const [comment, setComment] = useState('');
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [geoLocation, setGeoLocation] = useState<{ lat: number; lon: number } | null>(null);

  // Получаем геолокацию при загрузке
  React.useEffect(() => {
    if ('geolocation' in navigator) {
      navigator.geolocation.getCurrentPosition(
        (pos) => setGeoLocation({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
        () => console.warn('Geolocation not available'),
        { enableHighAccuracy: true }
      );
    }
  }, []);

  const handlePhotoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setPhotoFile(file);
      const reader = new FileReader();
      reader.onloadend = () => setPhotoPreview(reader.result as string);
      reader.readAsDataURL(file);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!taskId) return;

    if (!motoHours || parseFloat(motoHours) <= 0) {
      showToast.error('Укажите моточасы');
      return;
    }

    try {
      setLoading(true);

      const formData = new FormData();
      formData.append('moto_hours', motoHours);
      formData.append('odometer', odometer || '0');
      formData.append('fuel_used', fuelUsed || '0');
      formData.append('comment', comment);
      if (photoFile) {
        formData.append('photo', photoFile);
      }

      await apiClient.post(`/driver/shifts/${taskId}/report`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      showToast.success('✅ Отчёт отправлен!');
      navigate('/driver/dashboard');
    } catch (err: any) {
      showToast.error('Ошибка: ' + (err?.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-blue-700 text-white px-4 py-4 sticky top-0 z-10 shadow-md">
        <div className="flex items-center gap-3 max-w-lg mx-auto">
          <button
            onClick={() => navigate('/driver/dashboard')}
            className="text-white opacity-80 hover:opacity-100"
          >
            ← Назад
          </button>
          <h1 className="text-lg font-bold">📝 Отчёт по смене</h1>
        </div>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="max-w-lg mx-auto px-4 py-6 space-y-5">
        {/* Моточасы */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            ⏱️ Моточасы *
          </label>
          <input
            type="number"
            step="0.5"
            min="0"
            value={motoHours}
            onChange={(e) => setMotoHours(e.target.value)}
            required
            className="w-full border border-gray-300 rounded-lg px-4 py-3 text-lg focus:ring-2 focus:ring-blue-500 outline-none"
            placeholder="Например: 8.5"
          />
        </div>

        {/* Одометр */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            🛣️ Одометр (км)
          </label>
          <input
            type="number"
            min="0"
            value={odometer}
            onChange={(e) => setOdometer(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-4 py-3 text-lg focus:ring-2 focus:ring-blue-500 outline-none"
            placeholder="Например: 12500"
          />
        </div>

        {/* Расход топлива */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            ⛽ Израсходовано топлива (л)
          </label>
          <input
            type="number"
            step="0.1"
            min="0"
            value={fuelUsed}
            onChange={(e) => setFuelUsed(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-4 py-3 text-lg focus:ring-2 focus:ring-blue-500 outline-none"
            placeholder="Например: 45.5"
          />
        </div>

        {/* Комментарий */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            💬 Комментарий
          </label>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            rows={3}
            className="w-full border border-gray-300 rounded-lg px-4 py-3 text-base focus:ring-2 focus:ring-blue-500 outline-none resize-none"
            placeholder="Опишите выполненные работы..."
          />
        </div>

        {/* Фото */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            📷 Фотоотчёт
          </label>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            capture="environment"
            onChange={handlePhotoChange}
            className="hidden"
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="w-full border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-blue-400 hover:bg-blue-50 transition-colors"
          >
            {photoPreview ? (
              <div className="relative">
                <img src={photoPreview} alt="Preview" className="w-full h-48 object-cover rounded-lg" />
                <div className="absolute bottom-2 right-2 bg-black/60 text-white text-xs px-2 py-1 rounded">
                  Нажмите чтобы изменить
                </div>
              </div>
            ) : (
              <div>
                <div className="text-3xl mb-2">📷</div>
                <div className="text-sm text-gray-500">Нажмите чтобы сделать фото</div>
                <div className="text-xs text-gray-400 mt-1">или выбрать из галереи</div>
              </div>
            )}
          </button>
        </div>

        {/* Геолокация */}
        {geoLocation && (
          <div className="bg-blue-50 rounded-lg p-3 text-xs text-blue-700 flex items-center gap-2">
            <span>📍</span>
            <span>Геолокация: {geoLocation.lat.toFixed(5)}, {geoLocation.lon.toFixed(5)}</span>
          </div>
        )}

        {/* Submit */}
        <button
          type="submit"
          disabled={loading}
          className="w-full bg-green-600 text-white py-4 rounded-xl font-bold text-lg hover:bg-green-700 transition-colors disabled:opacity-50 shadow-lg"
        >
          {loading ? '⏳ Отправка...' : '✅ Отправить отчёт'}
        </button>
      </form>
    </div>
  );
};

export default ShiftReportPage;