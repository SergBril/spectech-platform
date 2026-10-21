import React, { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import apiClient from '../api/client';

interface MarketplaceRequest {
  id: number;
  vehicle_category_id: number | null;
  vehicle_category_name: string | null;
  work_type: string | null;
  object_address: string | null;
  planned_start: string | null;
  planned_end: string | null;
  shift_duration_hours: number | null;
  client_rate: number | null;
  rate_type: string | null;
  marketplace_mode: string;
  payment_terms_days: number;
  is_extended_payment: boolean;
  requirements: Record<string, any> | null;
  priority: string;
  created_at: string | null;
}

const MarketplacePage: React.FC = () => {
  const [requests, setRequests] = useState<MarketplaceRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterCategory, setFilterCategory] = useState<string>('all');

  useEffect(() => {
    loadRequests();
  }, [filterCategory]);

  const loadRequests = async () => {
    setLoading(true);
    try {
      const params: any = { limit: 100 };
      if (filterCategory !== 'all') params.category_id = parseInt(filterCategory);
      const res = await apiClient.get('/public/marketplace/requests', { params });
      setRequests(Array.isArray(res.data) ? res.data : []);
    } catch (err) {
      console.error('Failed to load marketplace requests:', err);
      setRequests([]);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (iso: string | null) => {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' });
  };

  return (
    <Layout>
      <div className="p-6 max-w-7xl mx-auto">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold text-gray-900">🌐 Маркетплейс заявок</h1>
          <select
            value={filterCategory}
            onChange={(e) => setFilterCategory(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
          >
            <option value="all">Все категории</option>
            <option value="2">Экскаваторы</option>
            <option value="3">Самосвалы</option>
            <option value="4">Автокраны</option>
            <option value="5">Бульдозеры</option>
            <option value="6">Погрузчики</option>
          </select>
        </div>

        {loading ? (
          <div className="flex justify-center py-12">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600"></div>
          </div>
        ) : requests.length === 0 ? (
          <div className="text-center py-12 bg-gray-50 rounded-lg">
            <p className="text-xl text-gray-500 mb-2">📭 Нет доступных заявок</p>
            <p className="text-sm text-gray-400">Новые заявки появятся здесь автоматически</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {requests.map((req) => (
              <div key={req.id} className="bg-white border rounded-lg shadow-sm hover:shadow-md transition-shadow overflow-hidden">
                {/* Payment warning banner */}
                {req.is_extended_payment && (
                  <div className="bg-red-50 border-b border-red-200 px-4 py-2 flex items-center gap-2">
                    <span className="text-red-600 animate-pulse">⏰</span>
                    <span className="text-sm font-medium text-red-800">
                      Оплата: {req.payment_terms_days} дн. (стандарт 7)
                    </span>
                  </div>
                )}

                <div className="p-4 space-y-3">
                  <div className="flex justify-between items-start">
                    <div>
                      <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium mb-1 ${
                        req.marketplace_mode === 'owner_dispatcher'
                          ? 'bg-orange-100 text-orange-800'
                          : 'bg-purple-100 text-purple-800'
                      }`}>
                        {req.marketplace_mode === 'owner_dispatcher' ? '📋 Диспетчер' : '🏪 Заказчик'}
                      </span>
                      <h3 className="font-semibold text-gray-900">
                        {req.vehicle_category_name || 'Техника'} — {req.work_type || 'Работы'}
                      </h3>
                    </div>
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                      req.priority === 'urgent' ? 'bg-red-100 text-red-800' :
                      req.priority === 'high' ? 'bg-orange-100 text-orange-800' :
                      'bg-gray-100 text-gray-600'
                    }`}>
                      {req.priority === 'urgent' ? '🔥 Срочно' :
                       req.priority === 'high' ? '⬆️ Высокий' : 'Обычный'}
                    </span>
                  </div>

                  <div className="text-sm text-gray-600 space-y-1">
                    <p>📍 {req.object_address || 'Адрес не указан'}</p>
                    <p>📅 {formatDate(req.planned_start)} — {formatDate(req.planned_end)}</p>
                    {req.shift_duration_hours && <p>⏱ {req.shift_duration_hours} ч/смена</p>}
                    {req.client_rate && (
                      <p className="font-medium text-blue-700">
                        💰 {req.client_rate} ₽/{req.rate_type === 'hourly' ? 'час' : 'смена'}
                      </p>
                    )}
                    {!req.is_extended_payment && (
                      <p className="text-green-600 text-xs">✅ Оплата: {req.payment_terms_days} дн.</p>
                    )}
                  </div>

                  {req.requirements && Object.keys(req.requirements).length > 0 && (
                    <div className="pt-2 border-t">
                      <p className="text-xs text-gray-500 mb-1">Требования:</p>
                      <div className="flex flex-wrap gap-1">
                        {Object.entries(req.requirements).map(([key, val]) => (
                          <span key={key} className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded text-xs">
                            {key}: {val}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  <button className="w-full mt-2 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors text-sm font-medium">
                    Откликнуться
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Layout>
  );
};

export default MarketplacePage;
