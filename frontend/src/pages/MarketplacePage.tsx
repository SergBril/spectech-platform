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
  const [respondingId, setRespondingId] = useState<number | null>(null);
  const [myVehicles, setMyVehicles] = useState<any[]>([]);
  const [showVehicleModal, setShowVehicleModal] = useState(false);
  const [selectedRequest, setSelectedRequest] = useState<MarketplaceRequest | null>(null);
  const [selectedVehicleId, setSelectedVehicleId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [filterCategory, setFilterCategory] = useState<string>('all');
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(0);
  const pageSize = 12;

  useEffect(() => {
    loadRequests();
  }, [filterCategory, page]);

  const loadRequests = async () => {
    setLoading(true);
    try {
      const params: any = { limit: pageSize, offset: page * pageSize };
      if (filterCategory !== 'all') params.category_id = parseInt(filterCategory);
      const res = await apiClient.get('/public/marketplace/requests', { params });
      const data = res.data;
      setRequests(Array.isArray(data) ? data : data?.items || []);
      setTotalCount(data?.total ?? (Array.isArray(data) ? data.length : 0));
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

  const handleRespond = async (req: MarketplaceRequest) => {
    setSelectedRequest(req);
    setRespondingId(req.id);
    try {
      const res = await apiClient.get('/vehicles', { params: { limit: 50 } });
      const vehicles = Array.isArray(res.data) ? res.data : res.data?.items || [];
      // Filter only marketplace-agreed vehicles matching category
      const eligible = vehicles.filter((v: any) => 
        v.marketplace_commission_agreed && 
        (!req.vehicle_category_id || v.category_id === req.vehicle_category_id)
      );
      setMyVehicles(eligible);
      setSelectedVehicleId(eligible.length === 1 ? eligible[0].id : null);
      setShowVehicleModal(true);
    } catch (err) {
      console.error('Failed to load vehicles:', err);
      alert('Ошибка загрузки техники');
    } finally {
      setRespondingId(null);
    }
  };

  const submitResponse = async () => {
    if (!selectedRequest || !selectedVehicleId) return;
    setRespondingId(selectedRequest.id);
    try {
      const res = await apiClient.post(`/public/marketplace/requests/${selectedRequest.id}/respond`, {
        vehicle_id: selectedVehicleId,
      });
      alert(res.data.message || '✅ Отклик отправлен!');
      setShowVehicleModal(false);
      setSelectedRequest(null);
      setSelectedVehicleId(null);
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Ошибка отправки отклика';
      alert('❌ ' + msg);
    } finally {
      setRespondingId(null);
    }
  };

  return (
    <Layout>
      <div className="p-6 max-w-7xl mx-auto">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold text-gray-900">🌐 Маркетплейс заявок</h1>
          <div className="flex gap-3 items-center">
            <button
              onClick={() => window.open('/api/v1/public/marketplace/requests/export', '_blank')}
              className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-sm font-medium flex items-center gap-2"
            >
              📥 Экспорт Excel
            </button>
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
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="font-semibold text-gray-900">
                          {req.vehicle_category_name || 'Техника'} — {req.work_type || 'Работы'}
                        </h3>
                      </div>
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

                  <button 
                    onClick={(e) => { e.stopPropagation(); handleRespond(req); }}
                    disabled={respondingId === req.id}
                    className="w-full mt-2 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {respondingId === req.id ? '⏳ Отправка...' : '✋ Откликнуться'}
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* Pagination */}
          {totalCount > pageSize && (
            <div className="flex justify-center items-center gap-4 mt-6">
              <button onClick={() => setPage(Math.max(0, page - 1))} disabled={page === 0}
                className="px-4 py-2 border rounded-lg disabled:opacity-50 hover:bg-gray-50">← Назад</button>
              <span className="text-sm text-gray-600">
                Стр. {page + 1} из {Math.ceil(totalCount / pageSize)} ({totalCount} заявок)
              </span>
              <button onClick={() => setPage(page + 1)} disabled={(page + 1) * pageSize >= totalCount}
                className="px-4 py-2 border rounded-lg disabled:opacity-50 hover:bg-gray-50">Вперёд →</button>
            </div>
          )}
        )}
      </div>

      {/* Vehicle Selection Modal */}
      {showVehicleModal && selectedRequest && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full max-h-[80vh] overflow-y-auto">
            <div className="p-6 border-b">
              <h2 className="text-xl font-bold text-gray-900">✋ Отклик на заявку</h2>
              <p className="text-sm text-gray-500 mt-1">
                {selectedRequest.vehicle_category_name} — {selectedRequest.work_type}
              </p>
              <p className="text-sm text-gray-500">📍 {selectedRequest.object_address}</p>
            </div>

            <div className="p-6 space-y-3">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Выберите технику для отклика:
              </label>
              
              {myVehicles.length === 0 ? (
                <div className="text-center py-8 bg-yellow-50 rounded-lg">
                  <p className="text-yellow-800 font-medium">⚠️ Нет подходящей техники</p>
                  <p className="text-sm text-yellow-600 mt-1">
                    Убедитесь, что у вас есть техника категории «{selectedRequest.vehicle_category_name}» 
                    с согласием на комиссию маркетплейса.
                  </p>
                </div>
              ) : (
                myVehicles.map((v: any) => (
                  <label key={v.id} className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all ${
                    selectedVehicleId === v.id 
                      ? 'border-blue-500 bg-blue-50 ring-2 ring-blue-200' 
                      : 'border-gray-200 hover:border-blue-300 hover:bg-gray-50'
                  }`}>
                    <input type="radio" name="responseVehicle" value={v.id}
                      checked={selectedVehicleId === v.id}
                      onChange={() => setSelectedVehicleId(v.id)}
                      className="accent-blue-600" />
                    <div className="flex-1">
                      <div className="font-medium text-gray-900">{v.name}</div>
                      <div className="text-xs text-gray-500">
                        Статус: {v.status} | Комиссия: {v.marketplace_commission_rate || 10}%
                      </div>
                    </div>
                  </label>
                ))
              )}
            </div>

            <div className="p-6 border-t flex gap-3 justify-end">
              <button onClick={() => { setShowVehicleModal(false); setSelectedRequest(null); }}
                className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors">
                Отмена
              </button>
              <button onClick={submitResponse}
                disabled={!selectedVehicleId || respondingId !== null}
                className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed font-medium">
                {respondingId ? '⏳ Отправка...' : '✅ Подтвердить отклик'}
              </button>
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
};

export default MarketplacePage;
