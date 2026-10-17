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
  const [activeTab, setActiveTab] = useState<'vehicles' | 'companies' | 'requests'>('requests');

  const [availableOnly, setAvailableOnly] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [priceMin, setPriceMin] = useState<string>('');
  const [priceMax, setPriceMax] = useState<string>('');
  const [sortBy, setSortBy] = useState<SortOption>('default');
  const [showFilters, setShowFilters] = useState(false);

  const [marketplaceRequests, setMarketplaceRequests] = useState<any[]>([]);
  const [loadingRequests, setLoadingRequests] = useState(false);
  const [offerModal, setOfferModal] = useState<{ requestId: number; workType: string; address: string; vehicleCategoryId: number | null } | null>(null);
  const [myVehicles, setMyVehicles] = useState<{ id: number; name: string }[]>([]);
  const [offerForm, setOfferForm] = useState({
    vehicle_id: '',
    offered_price: '',
    price_type: 'per_shift',
    message: '',
    estimated_arrival_minutes: '',
  });
  const [submittingOffer, setSubmittingOffer] = useState(false);

  // Filter vehicles by request category
  const filteredMyVehicles = useMemo(() => {
    if (!offerModal?.vehicleCategoryId) return myVehicles;
    return myVehicles.filter((v: any) => {
      // Direct match or parent category match
      return v.category_id === offerModal.vehicleCategoryId ||
             v.parent_category_id === offerModal.vehicleCategoryId;
    });
  }, [myVehicles, offerModal]);
  const [offerError, setOfferError] = useState('');

  useEffect(() => {
    fetchData();
    fetchMarketplaceRequests();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [vehiclesRes, companiesRes] = await Promise.all([
        apiClient.get('/public/vehicles'),
        apiClient.get('/public/companies'),
      ]);
      setVehicles(Array.isArray(vehiclesRes.data) ? vehiclesRes.data : []);
      setCompanies(Array.isArray(companiesRes.data) ? companiesRes.data : []);
    } catch (error) {
      console.error('Error fetching marketplace data:', error);
      setVehicles([]);
      setCompanies([]);
    } finally {
      setLoading(false);
    }
  };

  const fetchMarketplaceRequests = async () => {
    setLoadingRequests(true);
    try {
      const res = await apiClient.get('/marketplace/requests', { params: { limit: 100 } });
      setMarketplaceRequests(Array.isArray(res.data) ? res.data : []);
    } catch (e) {
      console.error('Failed to load marketplace requests:', e);
      setMarketplaceRequests([]);
    } finally {
      setLoadingRequests(false);
    }
  };

  const fetchMyVehicles = async () => {
    try {
      const res = await apiClient.get('/vehicles', { params: { limit: 500 } });
      const list = Array.isArray(res.data) ? res.data : (res.data?.items || []);
      setMyVehicles(list.map((v: any) => ({ id: v.id, name: v.name || `Техника #${v.id}`, category_id: v.category_id, parent_category_id: v.subcategory_id ? v.category_id : null })));
    } catch { /* ignore */ }
  };

  useEffect(() => {
    if (activeTab === 'requests') {
      fetchMarketplaceRequests();
      fetchMyVehicles();
    }
  }, [activeTab]);

  const categories = useMemo(() => {
    const unique = new Set<string>();
    vehicles.forEach((v) => { if (v.category_name) unique.add(v.category_name); });
    return Array.from(unique).sort();
  }, [vehicles]);

  const filteredVehicles = useMemo(() => {
    let result = [...vehicles];
    if (availableOnly) result = result.filter((v) => v.is_available_for_rent);
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      result = result.filter((v) => v.name.toLowerCase().includes(q) || v.owner_company_name.toLowerCase().includes(q) || v.category_name?.toLowerCase().includes(q));
    }
    if (selectedCategory !== 'all') result = result.filter((v) => v.category_name === selectedCategory);
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
    switch (sortBy) {
      case 'price_asc': result.sort((a, b) => (a.hourly_rate || 0) - (b.hourly_rate || 0)); break;
      case 'price_desc': result.sort((a, b) => (b.hourly_rate || 0) - (a.hourly_rate || 0)); break;
      case 'year_desc': result.sort((a, b) => b.year - a.year); break;
      case 'year_asc': result.sort((a, b) => a.year - b.year); break;
      case 'name_asc': result.sort((a, b) => a.name.localeCompare(b.name, 'ru')); break;
    }
    return result;
  }, [vehicles, availableOnly, searchQuery, selectedCategory, priceMin, priceMax, sortBy]);

  const hasActiveFilters = searchQuery.trim() !== '' || selectedCategory !== 'all' || priceMin !== '' || priceMax !== '' || sortBy !== 'default' || !availableOnly;
  const resetFilters = () => { setSearchQuery(''); setSelectedCategory('all'); setPriceMin(''); setPriceMax(''); setSortBy('default'); setAvailableOnly(true); };

  const getStatusBadge = (status: string) => {
    const colors: Record<string, string> = { free: 'bg-green-100 text-green-800', busy: 'bg-red-100 text-red-800', maintenance: 'bg-yellow-100 text-yellow-800' };
    const labels: Record<string, string> = { free: 'Свободна', busy: 'Занята', maintenance: 'На ТО' };
    return <span className={`px-2 py-1 rounded-full text-xs font-medium ${colors[status] || 'bg-gray-100'}`}>{labels[status] || status}</span>;
  };

  const getPriorityBadge = (priority: string) => {
    const map: Record<string, string> = {
      urgent: 'bg-red-100 text-red-800',
      high: 'bg-orange-100 text-orange-800',
      normal: 'bg-blue-100 text-blue-800',
      low: 'bg-gray-100 text-gray-600',
    };
    const labels: Record<string, string> = { urgent: 'Срочный', high: 'Высокий', normal: 'Обычный', low: 'Низкий' };
    return <span className={`px-2 py-1 rounded-full text-xs font-medium ${map[priority] || map.normal}`}>{labels[priority] || priority}</span>;
  };

  const handleOfferSubmit = async () => {
    if (!offerModal) return;
    setSubmittingOffer(true);
    setOfferError('');
    try {
      await apiClient.post(`/marketplace/requests/${offerModal.requestId}/offers`, {
        vehicle_id: parseInt(offerForm.vehicle_id),
        offered_price: parseFloat(offerForm.offered_price),
        price_type: offerForm.price_type,
        message: offerForm.message || undefined,
        estimated_arrival_minutes: offerForm.estimated_arrival_minutes ? parseInt(offerForm.estimated_arrival_minutes) : undefined,
      });
      setOfferModal(null);
      setOfferForm({ vehicle_id: '', offered_price: '', price_type: 'per_shift', message: '', estimated_arrival_minutes: '' });
      fetchMarketplaceRequests();
    } catch (e: any) {
      setOfferError(e.response?.data?.detail || 'Ошибка при отправке отклика');
    } finally {
      setSubmittingOffer(false);
    }
  };

  return (
    <Layout>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">🎯 Маркетплейс спецтехники</h1>
          <p className="text-gray-600">Каталог доступной техники, компаний и заявок</p>
        </div>

        {/* Табы */}
        <div className="mb-6 border-b border-gray-200">
          <nav className="-mb-px flex space-x-8">
            {(['vehicles', 'companies', 'requests'] as const).map((tab) => (
              <button key={tab} onClick={() => setActiveTab(tab)}
                className={`py-4 px-1 border-b-2 font-medium text-sm ${activeTab === tab ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}`}>
                {tab === 'vehicles' && `🚜 Техника (${vehicles.length})`}
                {tab === 'companies' && `🏢 Компании (${companies.length})`}
                {tab === 'requests' && `📋 Заявки (${marketplaceRequests.length})`}
              </button>
            ))}
          </nav>
        </div>

        {/* Фильтры для техники */}
        {activeTab === 'vehicles' && (
          <div className="mb-6 bg-white rounded-lg shadow-sm border border-gray-200 p-4">
            <div className="flex flex-col md:flex-row md:items-center gap-3">
              <div className="flex-1 relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">🔍</span>
                <input type="text" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Поиск по названию, категории, владельцу..."
                  className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none" />
              </div>
              <select value={sortBy} onChange={(e) => setSortBy(e.target.value as SortOption)}
                className="px-4 py-2 border border-gray-300 rounded-md text-sm">
                <option value="default">По умолчанию</option>
                <option value="price_asc">Цена ↑</option>
                <option value="price_desc">Цена ↓</option>
                <option value="year_desc">Сначала новые</option>
                <option value="name_asc">По названию</option>
              </select>
              {hasActiveFilters && <button onClick={resetFilters} className="px-4 py-2 text-sm text-red-600 hover:bg-red-50 rounded-md">✕ Сбросить</button>}
            </div>
            <div className="mt-4 pt-4 border-t border-gray-100 text-sm text-gray-600">
              Найдено: <strong>{filteredVehicles.length}</strong> из {vehicles.length}
            </div>
          </div>
        )}

        {/* Загрузка */}
        {(loading || loadingRequests) ? (
          <div className="flex justify-center items-center py-20">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
          </div>
        ) : (
          <>
            {/* ===== ТЕХНИКА ===== */}
            {activeTab === 'vehicles' && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {filteredVehicles.map((vehicle) => (
                  <div key={vehicle.id} className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden hover:shadow-md transition-shadow">
                    <div className="h-48 bg-gradient-to-br from-blue-100 to-blue-200 flex items-center justify-center"><span className="text-6xl">🚜</span></div>
                    <div className="p-4">
                      <div className="flex items-start justify-between mb-2">
                        <h3 className="text-lg font-semibold text-gray-900">{vehicle.name}</h3>
                        {getStatusBadge(vehicle.status)}
                      </div>
                      <p className="text-sm text-gray-600 mb-3">{vehicle.category_name} • {vehicle.year} год</p>
                      <p className="text-sm font-medium text-gray-900 mb-3">{vehicle.owner_company_name}</p>
                      <div className="grid grid-cols-2 gap-2 text-sm border-t pt-3">
                        <div><p className="text-gray-500 text-xs">Почасовая:</p><p className="font-semibold">{vehicle.hourly_rate ? `${vehicle.hourly_rate} ₽/ч` : '—'}</p></div>
                        <div><p className="text-gray-500 text-xs">Посменная:</p><p className="font-semibold">{vehicle.shift_rate ? `${vehicle.shift_rate} ₽/см` : '—'}</p></div>
                      </div>
                    </div>
                  </div>
                ))}
                {filteredVehicles.length === 0 && <div className="col-span-full text-center py-12 text-gray-500 text-lg">Нет доступной техники</div>}
              </div>
            )}

            {/* ===== КОМПАНИИ ===== */}
            {activeTab === 'companies' && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {companies.map((company) => (
                  <div key={company.id} onClick={() => navigate(`/companies/${company.id}`)}
                    className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-lg cursor-pointer">
                    <div className="flex items-center space-x-2 mb-3">
                      <span className="text-3xl">🏢</span>
                      <h3 className="text-lg font-semibold text-gray-900">{company.name}</h3>
                    </div>
                    {company.description && <p className="text-sm text-gray-600 mb-3 line-clamp-3">{company.description}</p>}
                    <div className="space-y-1 text-sm text-gray-600">
                      {company.city && <div>📍 {company.city}</div>}
                      <div>🚜 {company.vehicles_count} ед. техники</div>
                    </div>
                  </div>
                ))}
                {companies.length === 0 && <div className="col-span-full text-center py-12 text-gray-500 text-lg">Нет компаний</div>}
              </div>
            )}

            {/* ===== ЗАЯВКИ (ЭТОТ БЛОК ОТСУТСТВОВАЛ!) ===== */}
            {activeTab === 'requests' && (
              <div className="space-y-4">
                {marketplaceRequests.length === 0 ? (
                  <div className="text-center py-12 text-gray-500 text-lg">Заявок пока нет</div>
                ) : (
                  marketplaceRequests.map((req) => (
                    <div key={req.id} className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow">
                      <div className="flex items-start justify-between mb-3">
                        <div>
                          <h3 className="text-lg font-semibold text-gray-900">{req.work_type}</h3>
                          <p className="text-sm text-gray-600 mt-1">📍 {req.object_address}</p>
                        </div>
                        <div className="flex flex-col items-end space-y-1">
                          {getPriorityBadge(req.priority)}
                          {req.vehicle_category_name && (
                            <span className="text-xs bg-gray-100 text-gray-700 px-2 py-1 rounded-full">
                              {req.vehicle_category_name}
                            </span>
                          )}
                        </div>
                      </div>

                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm mb-4">
                        <div><p className="text-gray-500 text-xs">Период</p><p className="font-medium">{new Date(req.planned_start).toLocaleDateString('ru')} — {new Date(req.planned_end).toLocaleDateString('ru')}</p></div>
                        <div><p className="text-gray-500 text-xs">Смена</p><p className="font-medium">{req.shift_duration_hours} ч</p></div>
                        <div><p className="text-gray-500 text-xs">Ставка</p><p className="font-medium">{req.client_rate ? `${req.client_rate.toLocaleString()} ₽/${req.rate_type === 'per_shift' ? 'см' : 'ч'}` : '—'}</p></div>
                        <div><p className="text-gray-500 text-xs">Бюджет</p><p className="font-medium">{req.estimated_amount ? `${req.estimated_amount.toLocaleString()} ₽` : '—'}</p></div>
                      </div>

                      <div className="flex items-center justify-between pt-3 border-t">
                        <p className="text-xs text-gray-400">Опубликовано: {new Date(req.published_at).toLocaleDateString('ru')}</p>
                        <button
                          onClick={() => { setOfferModal({ requestId: req.id, workType: req.work_type, address: req.object_address, vehicleCategoryId: req.vehicle_category_id || null }); fetchMyVehicles(); }}
                          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm font-medium"
                        >
                          💰 Предложить технику
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}
          </>
        )}
      </div>

      {/* Модальное окно отклика */}
      {offerModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
            <h3 className="text-lg font-bold mb-1">💰 Предложить технику</h3>
            <p className="text-sm text-gray-600 mb-4">{offerModal.workType} — {offerModal.address}</p>

            {offerError && <div className="mb-3 p-3 bg-red-50 text-red-700 rounded text-sm">{offerError}</div>}

            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Техника</label>
                <select value={offerForm.vehicle_id} onChange={(e) => setOfferForm({ ...offerForm, vehicle_id: e.target.value })}
                  className="w-full px-3 py-2 border rounded-md text-sm">
                  <option value="">Выберите технику...</option>
                  {filteredMyVehicles.map((v: any) => <option key={v.id} value={v.id}>{v.name}</option>)}
                </select>
                {filteredMyVehicles.length === 0 && <p className="text-xs text-gray-500 mt-1">{myVehicles.length > 0 ? "Нет техники подходящей категории" : "Нет доступной техники"}</p>}
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Цена (₽)</label>
                  <input type="number" value={offerForm.offered_price} onChange={(e) => setOfferForm({ ...offerForm, offered_price: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md text-sm" placeholder="0" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Тип цены</label>
                  <select value={offerForm.price_type} onChange={(e) => setOfferForm({ ...offerForm, price_type: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md text-sm">
                    <option value="per_shift">За смену</option>
                    <option value="per_hour">За час</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Комментарий</label>
                <textarea value={offerForm.message} onChange={(e) => setOfferForm({ ...offerForm, message: e.target.value })}
                  className="w-full px-3 py-2 border rounded-md text-sm" rows={2} placeholder="Дополнительная информация..." />
              </div>
            </div>

            <div className="flex space-x-3 mt-6">
              <button onClick={() => setOfferModal(null)} className="flex-1 px-4 py-2 border rounded-md text-sm hover:bg-gray-50">Отмена</button>
              <button onClick={handleOfferSubmit} disabled={submittingOffer || !offerForm.vehicle_id || !offerForm.offered_price}
                className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-md text-sm hover:bg-blue-700 disabled:opacity-50">
                {submittingOffer ? 'Отправка...' : 'Отправить'}
              </button>
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
};

export default MarketplacePage;
