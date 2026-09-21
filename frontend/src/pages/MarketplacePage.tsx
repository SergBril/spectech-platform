import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Navbar } from '../components/Navbar';

interface Vehicle {
  id: number;
  name: string;
  category_name: string;
  year: number;
  status: string;
  hourly_rate: number | null;
  shift_rate: number | null;
  is_available_for_rent: boolean;
  owner_company_name: string;
  photos: string | null;
}

interface Company {
  id: number;
  name: string;
  description: string | null;
  city: string | null;
  phone: string | null;
  rating: number;
  vehicles_count: number;
  is_verified: boolean;
}

export const MarketplacePage: React.FC = () => {
  const navigate = useNavigate();
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'vehicles' | 'companies'>('vehicles');
  const [availableOnly, setAvailableOnly] = useState(true);

  useEffect(() => {
    fetchData();
  }, [availableOnly]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const vehiclesUrl = availableOnly
        ? 'http://localhost:8000/api/v1/public/vehicles?available_only=true'
        : 'http://localhost:8000/api/v1/public/vehicles';

      const [vehiclesRes, companiesRes] = await Promise.all([
        fetch(vehiclesUrl),
        fetch('http://localhost:8000/api/v1/public/companies'),
      ]);

      // Безопасная обработка: если API вернул не массив — пустой массив
      let vehiclesData: Vehicle[] = [];
      let companiesData: Company[] = [];

      if (vehiclesRes.ok) {
        const data = await vehiclesRes.json();
        vehiclesData = Array.isArray(data) ? data : [];
      } else {
        console.warn('Failed to load vehicles:', vehiclesRes.status);
      }

      if (companiesRes.ok) {
        const data = await companiesRes.json();
        companiesData = Array.isArray(data) ? data : [];
      } else {
        console.warn('Failed to load companies:', companiesRes.status);
      }

      setVehicles(vehiclesData);
      setCompanies(companiesData);
    } catch (error) {
      console.error('Error fetching marketplace data:', error);
      setVehicles([]);
      setCompanies([]);
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      free: 'bg-green-100 text-green-800',
      busy: 'bg-red-100 text-red-800',
      maintenance: 'bg-yellow-100 text-yellow-800',
    };
    const labels: Record<string, string> = {
      free: 'Свободна',
      busy: 'Занята',
      maintenance: 'На ТО',
    };
    return (
      <span className={`px-2 py-1 rounded-full text-xs font-medium ${colors[status] || 'bg-gray-100'}`}>
        {labels[status] || status}
      </span>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Заголовок */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            🎯 Маркетплейс спецтехники
          </h1>
          <p className="text-gray-600">
            Каталог доступной техники и проверенных компаний-владельцев
          </p>
        </div>

        {/* Табы */}
        <div className="mb-6 border-b border-gray-200">
          <nav className="-mb-px flex space-x-8">
            <button
              onClick={() => setActiveTab('vehicles')}
              className={`py-4 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'vehicles'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              🚜 Техника ({vehicles.length})
            </button>
            <button
              onClick={() => setActiveTab('companies')}
              className={`py-4 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'companies'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              🏢 Компании ({companies.length})
            </button>
          </nav>
        </div>

        {/* Фильтры для техники */}
        {activeTab === 'vehicles' && (
          <div className="mb-6 flex items-center space-x-4">
            <label className="flex items-center space-x-2 cursor-pointer">
              <input
                type="checkbox"
                checked={availableOnly}
                onChange={(e) => setAvailableOnly(e.target.checked)}
                className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
              />
              <span className="text-sm text-gray-700">
                Только доступная для аренды
              </span>
            </label>
          </div>
        )}

        {/* Загрузка */}
        {loading ? (
          <div className="flex justify-center items-center py-20">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
          </div>
        ) : (
          <>
            {/* Каталог техники */}
            {activeTab === 'vehicles' && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {vehicles.map((vehicle) => (
                  <div
                    key={vehicle.id}
                    className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden hover:shadow-md transition-shadow"
                  >
                    {/* Фото или placeholder */}
                    <div className="h-48 bg-gradient-to-br from-blue-100 to-blue-200 flex items-center justify-center">
                      <span className="text-6xl">🚜</span>
                    </div>

                    <div className="p-4">
                      <div className="flex items-start justify-between mb-2">
                        <h3 className="text-lg font-semibold text-gray-900">
                          {vehicle.name}
                        </h3>
                        {getStatusBadge(vehicle.status)}
                      </div>

                      <p className="text-sm text-gray-600 mb-3">
                        {vehicle.category_name} • {vehicle.year} год
                      </p>

                      <div className="mb-3">
                        <p className="text-xs text-gray-500 mb-1">Владелец:</p>
                        <p className="text-sm font-medium text-gray-900">
                          {vehicle.owner_company_name}
                        </p>
                      </div>

                      {/* Ставки */}
                      <div className="border-t border-gray-200 pt-3 mt-3">
                        <div className="grid grid-cols-2 gap-2 text-sm">
                          <div>
                            <p className="text-gray-500 text-xs">Почасовая:</p>
                            <p className="font-semibold text-gray-900">
                              {vehicle.hourly_rate
                                ? `${vehicle.hourly_rate} ₽/час`
                                : '—'}
                            </p>
                          </div>
                          <div>
                            <p className="text-gray-500 text-xs">Посменная:</p>
                            <p className="font-semibold text-gray-900">
                              {vehicle.shift_rate
                                ? `${vehicle.shift_rate} ₽/смена`
                                : '—'}
                            </p>
                          </div>
                        </div>
                      </div>

                      {/* Кнопка */}
                      {vehicle.is_available_for_rent && (
                        <button
                          onClick={() => navigate('/requests')}
                          className="mt-4 w-full bg-blue-600 text-white py-2 rounded-md hover:bg-blue-700 text-sm font-medium"
                        >
                          Создать заявку
                        </button>
                      )}
                    </div>
                  </div>
                ))}

                {vehicles.length === 0 && (
                  <div className="col-span-full text-center py-12">
                    <p className="text-gray-500 text-lg">
                      Нет доступной техники
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* Каталог компаний */}
            {activeTab === 'companies' && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {companies.map((company) => (
                  <div
                    key={company.id}
                    className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center space-x-2">
                        <span className="text-3xl">🏢</span>
                        <div>
                          <h3 className="text-lg font-semibold text-gray-900">
                            {company.name}
                          </h3>
                          {company.is_verified && (
                            <span className="text-xs bg-green-100 text-green-800 px-2 py-1 rounded-full">
                              ✓ Проверено
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center space-x-1">
                        <span className="text-yellow-500">⭐</span>
                        <span className="text-sm font-medium">{company.rating}</span>
                      </div>
                    </div>

                    {company.description && (
                      <p className="text-sm text-gray-600 mb-3 line-clamp-3">
                        {company.description}
                      </p>
                    )}

                    <div className="space-y-2 text-sm">
                      {company.city && (
                        <div className="flex items-center text-gray-600">
                          <span className="mr-2">📍</span>
                          {company.city}
                        </div>
                      )}
                      {company.phone && (
                        <div className="flex items-center text-gray-600">
                          <span className="mr-2">📞</span>
                          {company.phone}
                        </div>
                      )}
                      <div className="flex items-center text-gray-600">
                        <span className="mr-2">🚜</span>
                        {company.vehicles_count} ед. техники
                      </div>
                    </div>
                  </div>
                ))}

                {companies.length === 0 && (
                  <div className="col-span-full text-center py-12">
                    <p className="text-gray-500 text-lg">
                      Нет компаний в каталоге
                    </p>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default MarketplacePage;
