import React, { useEffect, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import apiClient from '../api/client';

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

type SortOption = 'default' | 'price_asc' | 'price_desc' | 'year_desc' | 'year_asc' | 'name_asc';

export const MarketplacePage: React.FC = () => {
  const navigate = useNavigate();
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'vehicles' | 'companies'>('vehicles');

  // 🆕 Состояния фильтров
  const [availableOnly, setAvailableOnly] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [priceMin, setPriceMin] = useState<string>('');
  const [priceMax, setPriceMax] = useState<string>('');
  const [sortBy, setSortBy] = useState<SortOption>('default');
  const [showFilters, setShowFilters] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [vehiclesRes, companiesRes] = await Promise.all([
        apiClient.get('/public/vehicles'),
        apiClient.get('/public/companies'),
      ]);

      const vehiclesData = Array.isArray(vehiclesRes.data) ? vehiclesRes.data : [];
      const companiesData = Array.isArray(companiesRes.data) ? companiesRes.data : [];

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

  // 🆕 Извлечение уникальных категорий из загруженных данных
  const categories = useMemo(() => {
    const unique = new Set<string>();
    vehicles.forEach((v) => {
      if (v.category_name) unique.add(v.category_name);
    });
    return Array.from(unique).sort();
  }, [vehicles]);

  // 🆕 Применение фильтров и сортировки
  const filteredVehicles = useMemo(() => {
    let result = [...vehicles];

    // 1. Фильтр "только доступные"
    if (availableOnly) {
      result = result.filter((v) => v.is_available_for_rent);
    }

    // 2. Поиск по названию и владельцу
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase().trim();
      result = result.filter(
        (v) =>
          v.name.toLowerCase().includes(query) ||
          v.owner_company_name.toLowerCase().includes(query) ||
          v.category_name.toLowerCase().includes(query)
      );
    }

    // 3. Фильтр по категории
    if (selectedCategory !== 'all') {
      result = result.filter((v) => v.category_name === selectedCategory);
    }

    // 4. Фильтр по цене (hourly_rate)
    const min = priceMin ? parseFloat(priceMin) : null;
    const max = priceMax ? parseFloat(priceMax) : null;
    if (min !== null || max !== null) {
      result = result.filter((v) => {
        if (v.hourly_rate === null) return false;
        if (min !== null && v.hourly_rate < min) return false;
        if (max !== null && v.hourly_rate > max) return false;
        return true;
      });
    }

    // 5. Сортировка
    switch (sortBy) {
      case 'price_asc':
        result.sort((a, b) => (a.hourly_rate || 0) - (b.hourly_rate || 0));
        break;
      case 'price_desc':
        result.sort((a, b) => (b.hourly_rate || 0) - (a.hourly_rate || 0));
        break;
      case 'year_desc':
        result.sort((a, b) => b.year - a.year);
        break;
      case 'year_asc':
        result.sort((a, b) => a.year - b.year);
        break;
      case 'name_asc':
        result.sort((a, b) => a.name.localeCompare(b.name, 'ru'));
        break;
    }

    return result;
  }, [vehicles, availableOnly, searchQuery, selectedCategory, priceMin, priceMax, sortBy]);

  // 🆕 Есть ли активные фильтры
  const hasActiveFilters =
    searchQuery.trim() !== '' ||
    selectedCategory !== 'all' ||
    priceMin !== '' ||
    priceMax !== '' ||
    sortBy !== 'default' ||
    !availableOnly;

  // 🆕 Сбросить все фильтры
  const resetFilters = () => {
    setSearchQuery('');
    setSelectedCategory('all');
    setPriceMin('');
    setPriceMax('');
    setSortBy('default');
    setAvailableOnly(true);
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
      <span
        className={`px-2 py-1 rounded-full text-xs font-medium ${
          colors[status] || 'bg-gray-100'
        }`}
      >
        {labels[status] || status}
      </span>
    );
  };

  return (
    <Layout>
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

        {/* 🆕 Панель фильтров для техники */}
        {activeTab === 'vehicles' && (
          <div className="mb-6 bg-white rounded-lg shadow-sm border border-gray-200 p-4">
            {/* Верхняя строка: поиск + кнопка расширенных фильтров */}
            <div className="flex flex-col md:flex-row md:items-center gap-3">
              {/* Поиск */}
              <div className="flex-1 relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
                  🔍
                </span>
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Поиск по названию, категории, владельцу..."
                  className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                />
                {searchQuery && (
                  <button
                    onClick={() => setSearchQuery('')}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                    title="Очистить"
                  >
                    ✕
                  </button>
                )}
              </div>

              {/* Кнопка "Фильтры" на мобильных */}
              <button
                onClick={() => setShowFilters(!showFilters)}
                className="md:hidden flex items-center justify-center space-x-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-md text-sm font-medium"
              >
                <span>⚙️</span>
                <span>Фильтры {hasActiveFilters && '•'}</span>
              </button>

              {/* Быстрая сортировка (десктоп) */}
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as SortOption)}
                className="hidden md:block px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 outline-none text-sm"
              >
                <option value="default">По умолчанию</option>
                <option value="price_asc">Цена: по возрастанию</option>
                <option value="price_desc">Цена: по убыванию</option>
                <option value="year_desc">Сначала новые</option>
                <option value="year_asc">Сначала старые</option>
                <option value="name_asc">По названию (А-Я)</option>
              </select>

              {/* Кнопка сброса */}
              {hasActiveFilters && (
                <button
                  onClick={resetFilters}
                  className="px-4 py-2 text-sm text-red-600 hover:bg-red-50 rounded-md font-medium"
                >
                  ✕ Сбросить
                </button>
              )}
            </div>

            {/* Расширенные фильтры (сворачиваемые) */}
            <div className={`${showFilters ? 'block' : 'hidden'} md:block mt-4`}>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4 pt-4 border-t border-gray-100">
                {/* Категория */}
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    Категория
                  </label>
                  <select
                    value={selectedCategory}
                    onChange={(e) => setSelectedCategory(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                  >
                    <option value="all">Все категории</option>
                    {categories.map((cat) => (
                      <option key={cat} value={cat}>
                        {cat}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Цена от */}
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    Цена от (₽/час)
                  </label>
                  <input
                    type="number"
                    min="0"
                    value={priceMin}
                    onChange={(e) => setPriceMin(e.target.value)}
                    placeholder="0"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                  />
                </div>

                {/* Цена до */}
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    Цена до (₽/час)
                  </label>
                  <input
                    type="number"
                    min="0"
                    value={priceMax}
                    onChange={(e) => setPriceMax(e.target.value)}
                    placeholder="∞"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                  />
                </div>

                {/* Чекбокс "только доступная" */}
                <div className="flex items-end">
                  <label className="flex items-center space-x-2 cursor-pointer pb-2">
                    <input
                      type="checkbox"
                      checked={availableOnly}
                      onChange={(e) => setAvailableOnly(e.target.checked)}
                      className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-700">
                      Только доступная
                    </span>
                  </label>
                </div>
              </div>

              {/* Мобильная сортировка */}
              <div className="md:hidden mt-4">
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Сортировка
                </label>
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value as SortOption)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                >
                  <option value="default">По умолчанию</option>
                  <option value="price_asc">Цена: по возрастанию</option>
                  <option value="price_desc">Цена: по убыванию</option>
                  <option value="year_desc">Сначала новые</option>
                  <option value="year_asc">Сначала старые</option>
                  <option value="name_asc">По названию (А-Я)</option>
                </select>
              </div>
            </div>

            {/* Индикатор результатов */}
            <div className="mt-4 pt-4 border-t border-gray-100 text-sm text-gray-600">
              Найдено: <strong className="text-gray-900">{filteredVehicles.length}</strong> из {vehicles.length}
              {hasActiveFilters && (
                <span className="ml-2 text-blue-600">
                  (применены фильтры)
                </span>
              )}
            </div>
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
                {filteredVehicles.map((vehicle) => (
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
                        <h3 className="text-lg font-semibold text-gray-900 flex-1 mr-2">
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
                      <button
                        onClick={() => navigate(`/marketplace/${vehicle.id}`)}
                        disabled={!vehicle.is_available_for_rent}
                        className={`mt-4 w-full py-2 rounded-md text-sm font-medium transition-colors ${
                          vehicle.is_available_for_rent
                            ? 'bg-blue-600 text-white hover:bg-blue-700'
                            : 'bg-gray-200 text-gray-500 cursor-not-allowed'
                        }`}
                      >
                        {vehicle.is_available_for_rent ? 'Подробнее' : 'Недоступна'}
                      </button>
                    </div>
                  </div>
                ))}

                {filteredVehicles.length === 0 && (
                  <div className="col-span-full text-center py-12">
                    <p className="text-gray-500 text-lg mb-4">
                      {vehicles.length === 0
                        ? 'Нет доступной техники'
                        : 'По заданным фильтрам ничего не найдено'}
                    </p>
                    {hasActiveFilters && (
                      <button
                        onClick={resetFilters}
                        className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm font-medium"
                      >
                        Сбросить фильтры
                      </button>
                    )}
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
                    onClick={() => navigate(`/companies/${company.id}`)}
                    className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-lg hover:border-blue-300 transition-all cursor-pointer group"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center space-x-2">
                        <span className="text-3xl">🏢</span>
                        <div>
                          <h3 className="text-lg font-semibold text-gray-900 group-hover:text-blue-600 transition-colors">
                            {company.name} <span className="text-blue-500 opacity-0 group-hover:opacity-100 transition-opacity">→</span>
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
    </Layout>
  );
};

export default MarketplacePage;