import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { showToast } from '../../utils/toast';
import apiClient from '../../api/client';

interface Shift {
  id: number;
  shift_date: string;
  status: string;
  vehicle_id?: number;
  address?: string;
  description?: string;
}

interface SalaryRecord {
  id: number;
  period_start: string;
  period_end: string;
  shifts_count: number;
  total_hours: number;
  gross_amount: number;
  net_amount: number;
  status: string;
}

const STATUS_LABELS: Record<string, string> = {
  draft: 'Черновик',
  signed_by_operator: 'В работе',
  pending: 'Ожидает',
  in_progress: 'В работе',
  checked: 'Проверено',
  released: 'Выпущено',
  completed: 'Завершена',
  cancelled: 'Отменена',
};

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-yellow-100 text-yellow-800',
  signed_by_operator: 'bg-indigo-100 text-indigo-800',
  pending: 'bg-blue-100 text-blue-800',
  in_progress: 'bg-indigo-100 text-indigo-800',
  checked: 'bg-cyan-100 text-cyan-800',
  released: 'bg-teal-100 text-teal-800',
  completed: 'bg-green-100 text-green-800',
  cancelled: 'bg-red-100 text-red-800',
};

const formatMoney = (v: number) =>
  `${v.toLocaleString('ru-RU', { minimumFractionDigits: 2 })} ₽`;

export const DriverDashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [salary, setSalary] = useState<SalaryRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'shifts' | 'salary' | 'vehicle'>('shifts');
  const [assignedVehicles, setAssignedVehicles] = useState<any[]>([]);
  const [assignmentHistory, setAssignmentHistory] = useState<any[]>([]);
  const [loadingVehicle, setLoadingVehicle] = useState(false);

  const loadVehicleData = async () => {
    setLoadingVehicle(true);
    try {
      // Get current driver profile
      const meRes = await apiClient.get('/driver/me');
      const myProfile = meRes.data;
      const cid = myProfile.contractor_id;

      const vehRes = await apiClient.get('/vehicles', { params: { limit: 100 } });
      const allVeh = vehRes.data.items || vehRes.data;
      setAssignedVehicles(allVeh.filter((v: any) => v.assigned_driver_id === cid));

      const histRes = await apiClient.get(`/drivers/${cid}/history`);
      setAssignmentHistory(Array.isArray(histRes.data) ? histRes.data : []);
    } catch (err: any) {
      console.error('Failed to load vehicle data:', err);
      if (err?.response?.status === 404) {
        showToast.error('Профиль водителя не найден. Обратитесь к администратору.');
      } else {
        showToast.error('Ошибка загрузки данных о технике');
      }
    } finally { setLoadingVehicle(false); }
  };

  useEffect(() => { if (activeTab === 'vehicle') loadVehicleData(); }, [activeTab]);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [shiftsRes, salaryRes] = await Promise.allSettled([
        apiClient.get('/driver/my-shifts'),
        apiClient.get('/driver/my-salary'),
      ]);
      if (shiftsRes.status === 'fulfilled') setShifts(shiftsRes.value.data.shifts || []);
      if (salaryRes.status === 'fulfilled') setSalary(salaryRes.value.data.records || []);
    } catch (err: any) {
      if (err?.response?.status === 401) {
        navigate('/driver/login');
        return;
      }
      showToast.error('Ошибка загрузки данных');
    } finally {
      setLoading(false);
    }
  };

  const handleStartShift = async (taskId: number) => {
    try {
      await apiClient.post(`/driver/shifts/${taskId}/start`);
      showToast.success('▶️ Смена начата');
      loadData();
    } catch (err: any) {
      showToast.error('Ошибка: ' + (err?.response?.data?.detail || err.message));
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    navigate('/driver/login');
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-blue-700 text-white px-4 py-4 sticky top-0 z-10 shadow-md">
        <div className="flex items-center justify-between max-w-lg mx-auto">
          <div className="flex items-center gap-2">
            <span className="text-2xl">🚜</span>
            <h1 className="text-lg font-bold">Водитель</h1>
          </div>
          <button onClick={handleLogout} className="text-sm opacity-80 hover:opacity-100">
            Выход
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="max-w-lg mx-auto px-4 pt-4">
        <div className="flex bg-white rounded-lg p-1 shadow-sm mb-4">
          <button
            onClick={() => setActiveTab('shifts')}
            className={`flex-1 py-2.5 rounded-md text-sm font-medium transition-colors ${
              activeTab === 'shifts' ? 'bg-blue-600 text-white' : 'text-gray-600'
            }`}
          >
            📋 Смены
          </button>
          <button
            onClick={() => setActiveTab('salary')}
            className={`flex-1 py-2.5 rounded-md text-sm font-medium transition-colors ${
              activeTab === 'salary' ? 'bg-blue-600 text-white' : 'text-gray-600'
            }`}
          >
            💰 Зарплата
          </button>
          <button
            onClick={() => setActiveTab('vehicle')}
            className={`flex-1 py-2.5 rounded-md text-sm font-medium transition-colors ${
              activeTab === 'vehicle' ? 'bg-blue-600 text-white' : 'text-gray-600'
            }`}
          >
            🚜 Техника
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-lg mx-auto px-4 pb-8">
        {loading ? (
          <div className="flex justify-center py-12">
            <div className="w-8 h-8 border-4 border-blue-200 rounded-full animate-spin border-t-blue-600" />
          </div>
        ) : activeTab === 'shifts' ? (
          <div className="space-y-3">
            {shifts.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                <div className="text-4xl mb-3">📋</div>
                <p>Нет назначенных смен</p>
              </div>
            ) : (
              shifts.map((shift) => (
                <div key={shift.id} className="bg-white rounded-xl p-4 shadow-sm border border-gray-100">
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <div className="font-semibold text-gray-900">
                        {new Date(shift.shift_date).toLocaleDateString('ru-RU', {
                          weekday: 'short', day: 'numeric', month: 'long',
                        })}
                      </div>
                      {shift.address && (
                        <div className="text-sm text-gray-500 mt-1">📍 {shift.address}</div>
                      )}
                    </div>
                    <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${STATUS_COLORS[shift.status] || 'bg-gray-100 text-gray-800'}`}>
                      {STATUS_LABELS[shift.status] || shift.status}
                    </span>
                  </div>
                  {shift.description && (
                    <p className="text-sm text-gray-600 mb-3">{shift.description}</p>
                  )}
                  {(shift.status === 'draft' || shift.status === 'pending') && (
                    <button
                      onClick={() => handleStartShift(shift.id)}
                      className="w-full bg-blue-600 text-white py-2.5 rounded-lg font-medium hover:bg-blue-700 transition-colors"
                    >
                      ▶️ Начать смену
                    </button>
                  )}
                  {(shift.status === 'signed_by_operator' || shift.status === 'in_progress') && (
                    <button
                      onClick={() => navigate(`/driver/shift-report/${shift.id}`)}
                      className="w-full bg-orange-500 text-white py-2.5 rounded-lg font-medium hover:bg-orange-600 transition-colors"
                    >
                      📝 Завершить и отправить отчёт
                    </button>
                  )}
                  {(shift.status === 'in_progress' || shift.status === 'draft') && shift.status !== 'completed' && (
                    <button
                      onClick={() => navigate(`/driver/shift-report/${shift.id}`)}
                      className="w-full mt-2 bg-orange-500 text-white py-2.5 rounded-lg font-medium hover:bg-orange-600 transition-colors"
                    >
                      📝 Отправить отчёт
                    </button>
                  )}
                </div>
              ))
            )}
          </div>
        ) : activeTab === 'vehicle' ? (
          <div className="space-y-3">
            {loadingVehicle ? (
              <div className="flex justify-center py-12">
                <div className="w-8 h-8 border-4 border-blue-200 rounded-full animate-spin border-t-blue-600" />
              </div>
            ) : (
              <>
                {assignedVehicles.length > 0 && (
                  <div>
                    <h3 className="text-xs font-semibold text-gray-500 uppercase mb-2 px-1">Текущая техника</h3>
                    {assignedVehicles.map((v: any) => (
                      <div key={v.id} className="bg-white rounded-xl p-4 shadow-sm border border-gray-100 mb-3">
                        <div className="flex items-start gap-3">
                          <div className="text-3xl">🚜</div>
                          <div className="flex-1 min-w-0">
                            <h3 className="font-bold text-gray-900 truncate">{v.name}</h3>
                            <p className="text-sm text-gray-500">{v.psm_number || v.plate_number || '—'} • {v.category_name || ''}</p>
                            <p className="text-xs text-green-600 mt-1">✅ Назначена</p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                <div>
                  <h3 className="text-xs font-semibold text-gray-500 uppercase mb-2 px-1">История пересадок</h3>
                  {assignmentHistory.length === 0 ? (
                    <div className="text-center py-8 text-gray-500">
                      <div className="text-4xl mb-3">📭</div>
                      <p>История пуста</p>
                    </div>
                  ) : (
                    assignmentHistory.map((item: any) => (
                      <div key={item.id} className="bg-white rounded-xl p-4 shadow-sm border border-gray-100 mb-3">
                        <div className="flex items-start gap-3">
                          <div className="text-2xl mt-0.5">🚜</div>
                          <div className="flex-1 min-w-0">
                            <h3 className="font-semibold text-gray-900 truncate">{item.vehicle_name}</h3>
                            <p className="text-xs text-gray-500">{item.vehicle_plate || '—'}</p>
                            <div className="mt-1.5 flex flex-wrap gap-2 text-xs">
                              <span className="text-green-600">✅ с {new Date(item.assigned_at).toLocaleDateString('ru-RU')}</span>
                              {item.unassigned_at && <span className="text-red-500">❌ по {new Date(item.unassigned_at).toLocaleDateString('ru-RU')}</span>}
                              {!item.unassigned_at && <span className="text-blue-600 font-medium">🔵 Текущее</span>}
                            </div>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            {salary.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                <div className="text-4xl mb-3">💰</div>
                <p>Нет начислений зарплаты</p>
              </div>
            ) : (
              salary.map((rec) => (
                <div key={rec.id} className="bg-white rounded-xl p-4 shadow-sm border border-gray-100">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-gray-500">
                      {new Date(rec.period_start).toLocaleDateString('ru-RU')} —{' '}
                      {new Date(rec.period_end).toLocaleDateString('ru-RU')}
                    </span>
                    <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${
                      rec.status === 'approved' ? 'bg-green-100 text-green-800' :
                      rec.status === 'paid' ? 'bg-blue-100 text-blue-800' :
                      'bg-yellow-100 text-yellow-800'
                    }`}>
                      {rec.status === 'draft' ? 'Черновик' : rec.status === 'approved' ? 'Утверждено' : rec.status === 'paid' ? 'Выплачено' : rec.status}
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-center mb-3">
                    <div>
                      <div className="text-xs text-gray-400">Смен</div>
                      <div className="font-semibold text-gray-900">{rec.shifts_count}</div>
                    </div>
                    <div>
                      <div className="text-xs text-gray-400">Часов</div>
                      <div className="font-semibold text-gray-900">{rec.total_hours.toFixed(1)}</div>
                    </div>
                    <div>
                      <div className="text-xs text-gray-400">Начислено</div>
                      <div className="font-semibold text-gray-900">{formatMoney(rec.gross_amount)}</div>
                    </div>
                  </div>
                  <div className="bg-green-50 rounded-lg p-3 text-center">
                    <div className="text-xs text-green-600 uppercase font-medium">К выплате</div>
                    <div className="text-xl font-bold text-green-700">{formatMoney(rec.net_amount)}</div>
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default DriverDashboardPage;