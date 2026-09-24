import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { financeApi } from '../api/finance';
import { requestsApi } from '../api/requests';
import { companiesApi } from '../api/companies';
import { contractorsApi, type Contractor } from '../api/contractors';
import { showToast } from '../utils/toast';
import NotificationBell from '../components/NotificationBell';
import { TaxSystemSelector } from '../components/TaxSystemSelector';
import Navbar from '../components/Navbar';

export const ActCreatePage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const requestId = searchParams.get('request_id');
  const { user, logout, hasPermission } = useAuth();

  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [request, setRequest] = useState<any>(null);
  const [contractors, setContractors] = useState<Contractor[]>([]);
  const [searchContractor, setSearchContractor] = useState('');
  const [isManualTaxOverride, setIsManualTaxOverride] = useState(false);

  const [formData, setFormData] = useState({
    request_id: requestId ? parseInt(requestId) : 0,
    client_id: 0,
    act_date: new Date().toISOString().split('T')[0],
    total_amount: '0.00',
    comment: '',
    tax_system: 'osno',
    vat_rate: '22',
    is_vat_included: true,
  });

  const canCreate = hasPermission('finance', 'create');

  // Загрузка заявки
  useEffect(() => {
    if (requestId) {
      loadRequest(parseInt(requestId));
    } else {
      setPageLoading(false);
    }
  }, [requestId]);

  // Загрузка клиентов
  useEffect(() => {
    contractorsApi
      .getAll({ type: 'client', is_active: true, limit: 500 })
      .then(setContractors)
      .catch((err) => {
        console.error('Ошибка загрузки клиентов:', err);
      });
  }, []);

  // АВТОЗАГРУЗКА настроек компании
  useEffect(() => {
    if (user?.company_id && !isManualTaxOverride) {
      companiesApi
        .getTaxSettings(user.company_id)
        .then((settings) => {
          setFormData((prev) => ({
            ...prev,
            tax_system: settings.default_tax_system,
            vat_rate: settings.default_vat_rate.toString(),
            is_vat_included: settings.default_is_vat_included,
          }));
        })
        .catch((err) => {
          console.warn('Не удалось загрузить настройки компании:', err);
        });
    }
  }, [user]);

  const loadRequest = async (id: number) => {
    try {
      const req = await requestsApi.getById(id);
      setRequest(req);
      setFormData((prev) => ({
        ...prev,
        request_id: req.id,
        client_id: (req as any).client_id || 1,
        total_amount: String((req as any).estimated_amount || '0.00'),
      }));
    } catch (err) {
      showToast.error('Не удалось загрузить заявку');
      navigate('/requests');
    } finally {
      setPageLoading(false);
    }
  };

  const handleTaxSystemChange = (newSystem: string) => {
    setIsManualTaxOverride(true);
    setFormData((prev) => ({
      ...prev,
      tax_system: newSystem,
      vat_rate: newSystem !== 'osno' ? '0' : prev.vat_rate === '0' ? '22' : prev.vat_rate,
    }));
  };

  // 🆕 Обработчик выбора клиента с автоподстановкой tax_system
  const handleContractorChange = (contractorId: string) => {
    const id = parseInt(contractorId) || 0;
    setSearchContractor('');

    setFormData((prev) => {
      const newData = { ...prev, client_id: id };

      // Автоматически подставляем систему налогов клиента
      if (id && !isManualTaxOverride) {
        const contractor = contractors.find((c) => c.id === id);
        if (contractor?.tax_system) {
          newData.tax_system = contractor.tax_system;
          newData.vat_rate = contractor.tax_system !== 'osno' ? '0' : '22';
        }
      }

      return newData;
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canCreate) {
      showToast.error('Нет прав на создание акта');
      return;
    }

    if (!formData.client_id) {
      showToast.error('Выберите заказчика');
      return;
    }

    setLoading(true);
    try {
      const act = await financeApi.createAct({
        request_id: formData.request_id,
        client_id: formData.client_id,
        act_date: formData.act_date,
        total_amount: parseFloat(formData.total_amount),
        comment: formData.comment || undefined,
        tax_system: formData.tax_system,
        vat_rate: parseFloat(formData.vat_rate || '0'),
        is_vat_included: formData.is_vat_included,
      });
      showToast.success(`✅ Акт ${act.document_number} создан!`);
      navigate(`/requests/${requestId}`);
    } catch (err: any) {
      showToast.error('Ошибка: ' + (err?.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  // Получаем выбранного клиента для превью
  const selectedContractor = formData.client_id
    ? contractors.find((c) => c.id === formData.client_id)
    : null;

  if (pageLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="text-5xl mb-4 animate-pulse">⏳</div>
          <p className="text-gray-600">Загрузка...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <main className="max-w-3xl mx-auto py-8 px-4">
        <div className="bg-white rounded-lg shadow p-6">
          <h1 className="text-2xl font-bold text-gray-900 mb-6">📄 Создание акта</h1>

          {request && (
            <div className="bg-blue-50 border border-blue-200 rounded p-4 mb-6">
              <h3 className="font-semibold text-blue-900 mb-2">Заявка #{request.id}</h3>
              <p className="text-sm text-blue-800">🔧 {request.work_type}</p>
              <p className="text-sm text-blue-700">📍 {request.object_address}</p>
              <p className="text-sm text-blue-700">
                💵 Ожидаемая сумма: {(request as any).estimated_amount || '—'} ₽
              </p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">📅 Дата акта</label>
              <input
                type="date"
                value={formData.act_date}
                onChange={(e) => setFormData({ ...formData, act_date: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">💰 Сумма (₽)</label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={formData.total_amount}
                onChange={(e) => setFormData({ ...formData, total_amount: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                required
              />
            </div>

            {/* 🆕 Блок выбора заказчика */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">👤 Заказчик *</label>
              <input
                type="text"
                placeholder="Поиск по названию или ИНН..."
                value={searchContractor}
                onChange={(e) => setSearchContractor(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none mb-2"
              />
              <select
                value={formData.client_id || ''}
                onChange={(e) => handleContractorChange(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                required
              >
                <option value="">— Выберите заказчика —</option>
                {contractors
                  .filter(
                    (c) =>
                      !searchContractor ||
                      c.name.toLowerCase().includes(searchContractor.toLowerCase()) ||
                      c.inn?.toLowerCase().includes(searchContractor.toLowerCase()),
                  )
                  .map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} {c.inn ? `(ИНН: ${c.inn})` : ''}
                    </option>
                  ))}
              </select>

              {/* Превью реквизитов выбранного заказчика */}
              {selectedContractor && (
                <div className="mt-2 p-3 bg-blue-50 border border-blue-200 rounded text-xs text-blue-900">
                  <div className="font-semibold mb-1">{selectedContractor.name}</div>
                  {selectedContractor.inn && (
                    <div>
                      ИНН: {selectedContractor.inn}
                      {selectedContractor.kpp ? ` / КПП: ${selectedContractor.kpp}` : ''}
                    </div>
                  )}
                  {selectedContractor.legal_address && (
                    <div className="truncate">Адрес: {selectedContractor.legal_address}</div>
                  )}
                  {selectedContractor.tax_system && (
                    <div>
                      Система налогов:{' '}
                      <span className="font-medium">
                        {selectedContractor.tax_system === 'osno' && 'ОСНО'}
                        {selectedContractor.tax_system === 'usn_6' && 'УСН "Доходы"'}
                        {selectedContractor.tax_system === 'usn_15' && 'УСН "Доходы-Расходы"'}
                        {selectedContractor.tax_system === 'patent' && 'Патент'}
                        {selectedContractor.tax_system === 'npd' && 'НПД'}
                      </span>
                    </div>
                  )}
                </div>
              )}

              <button
                type="button"
                onClick={() => window.open('/contractors', '_blank')}
                className="mt-2 text-xs text-blue-600 hover:text-blue-800"
              >
                + Добавить нового клиента
              </button>
            </div>

            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <TaxSystemSelector
                value={formData.tax_system}
                onChange={handleTaxSystemChange}
                onVatRateChange={(rate) => {
                  setIsManualTaxOverride(true);
                  setFormData({ ...formData, vat_rate: rate });
                }}
              />

              {formData.tax_system === 'osno' && (
                <div className="mt-3 flex items-center">
                  <input
                    id="actVatIncluded"
                    type="checkbox"
                    checked={formData.is_vat_included}
                    onChange={(e) => {
                      setIsManualTaxOverride(true);
                      setFormData({ ...formData, is_vat_included: e.target.checked });
                    }}
                    className="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500"
                  />
                  <label htmlFor="actVatIncluded" className="ml-2 text-sm text-gray-700">
                    НДС включён в сумму (иначе — начисляется сверху)
                  </label>
                </div>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">💬 Комментарий</label>
              <textarea
                value={formData.comment}
                onChange={(e) => setFormData({ ...formData, comment: e.target.value })}
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                placeholder="Необязательное поле"
              />
            </div>

            <div className="flex gap-3 pt-4">
              <button
                type="submit"
                disabled={loading || !canCreate}
                className="flex-1 bg-blue-600 text-white py-3 rounded hover:bg-blue-700 disabled:opacity-50 font-semibold"
              >
                {loading ? '⏳ Создание...' : '✅ Создать акт'}
              </button>
              <button
                type="button"
                onClick={() => navigate(`/requests/${requestId}`)}
                className="flex-1 bg-gray-200 text-gray-800 py-3 rounded hover:bg-gray-300 font-semibold"
              >
                Отмена
              </button>
            </div>

            {!canCreate && (
              <p className="text-red-600 text-sm text-center">
                ⚠️ У вас нет прав на создание актов
              </p>
            )}
          </form>
        </div>
      </main>
    </div>
  );
};

export default ActCreatePage;
