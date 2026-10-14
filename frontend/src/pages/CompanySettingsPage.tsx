import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useCompany } from '../contexts/CompanyContext';
import { companiesApi, type CompanyTaxSettings } from '../api/companies';
import { TaxSystemSelector } from '../components/TaxSystemSelector';
import { showToast } from '../utils/toast';
import apiClient from '../api/client';
import Layout from '../components/Layout';

export const CompanySettingsPage: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { currentCompany, currentCompanyId } = useCompany();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savingRequisites, setSavingRequisites] = useState(false);
  const [activeTab, setActiveTab] = useState<'requisites' | 'tax'>('requisites');

  // Налоговые настройки
  const [taxSettings, setTaxSettings] = useState<CompanyTaxSettings>({
    default_tax_system: 'osno',
    default_vat_rate: 20,
    default_is_vat_included: true,
  });

  // Реквизиты
  const [requisites, setRequisites] = useState({
    name: '',
    legal_name: '',
    inn: '',
    kpp: '',
    ogrn: '',
    okpo: '',
    legal_address: '',
    actual_address: '',
    phone: '',
    email: '',
    bank_name: '',
    bik: '',
    checking_account: '',
    correspondent_account: '',
    director_name: '',
    director_position: '',
  });

  useEffect(() => {
    loadData();
  }, [currentCompanyId]);

  const loadData = async () => {
    if (!currentCompanyId) return;
    try {
      setLoading(true);
      const [taxData] = await Promise.all([
        companiesApi.getTaxSettings(currentCompanyId),
      ]);
      setTaxSettings(taxData);

      // Заполняем реквизиты из текущего контекста компании
      if (currentCompany) {
        const c = currentCompany as any;
        setRequisites({
          name: c.name || '',
          legal_name: c.legal_name || '',
          inn: c.inn || '',
          kpp: c.kpp || '',
          ogrn: c.ogrn || '',
          okpo: c.okpo || '',
          legal_address: c.legal_address || '',
          actual_address: c.actual_address || '',
          phone: c.phone || '',
          email: c.email || '',
          bank_name: c.bank_name || '',
          bik: c.bik || '',
          checking_account: c.checking_account || '',
          correspondent_account: c.correspondent_account || '',
          director_name: c.director_name || '',
          director_position: c.director_position || '',
        });
      }
    } catch (err: any) {
      showToast.error('Не удалось загрузить настройки');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveTax = async () => {
    if (!currentCompanyId) return;
    try {
      setSaving(true);
      await companiesApi.updateTaxSettings(currentCompanyId, taxSettings);
      showToast.success('Налоговые настройки сохранены');
    } catch (err: any) {
      showToast.error('Ошибка: ' + (err?.response?.data?.detail || err.message));
    } finally {
      setSaving(false);
    }
  };

  const handleSaveRequisites = async () => {
    if (!currentCompanyId) return;
    try {
      setSavingRequisites(true);
      await apiClient.patch(`/companies/${currentCompanyId}/requisites`, requisites);
      showToast.success('✅ Реквизиты сохранены');
    } catch (err: any) {
      showToast.error('Ошибка: ' + (err?.response?.data?.detail || err.message));
    } finally {
      setSavingRequisites(false);
    }
  };

  const handleTaxSystemChange = (newSystem: string) => {
    setTaxSettings((prev) => ({
      ...prev,
      default_tax_system: newSystem,
      default_vat_rate: newSystem !== 'osno' ? 0 : prev.default_vat_rate === 0 ? 20 : prev.default_vat_rate,
    }));
  };

  const handleRequisiteChange = (field: string, value: string) => {
    setRequisites((prev) => ({ ...prev, [field]: value }));
  };

  if (loading) {
    return (
      <Layout>
        <div className="min-h-[60vh] flex items-center justify-center">
          <div className="text-center">
            <div className="text-5xl mb-4 animate-pulse">⏳</div>
            <p className="text-gray-600">Загрузка...</p>
          </div>
        </div>
      </Layout>
    );
  }

  if (!currentCompanyId) {
    return (
      <Layout>
        <div className="p-8 text-center text-gray-500">Выберите компанию для редактирования настроек</div>
      </Layout>
    );
  }

  const Field = ({ label, field, placeholder, half }: { label: string; field: string; placeholder?: string; half?: boolean }) => (
    <div className={half ? 'flex-1 min-w-[250px]' : 'w-full'}>
      <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
      <input
        type="text"
        value={requisites[field as keyof typeof requisites]}
        onChange={(e) => handleRequisiteChange(field, e.target.value)}
        placeholder={placeholder}
        className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none transition-shadow"
      />
    </div>
  );

  const tabs = [
    { id: 'requisites' as const, label: '📄 Реквизиты', icon: '📄' },
    { id: 'tax' as const, label: '💼 Налоги', icon: '💼' },
  ];

  return (
    <Layout>
      <div className="p-6 max-w-4xl mx-auto space-y-6">
        {/* Заголовок */}
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">⚙️ Настройки компании</h1>
          <span className="text-sm text-gray-500 bg-gray-100 px-3 py-1 rounded-full">
            {currentCompany?.name}
          </span>
        </div>

        {/* Табы */}
        <div className="flex gap-1 bg-gray-100 p-1 rounded-lg w-fit">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
                activeTab === tab.id
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Вкладка: Реквизиты */}
        {activeTab === 'requisites' && (
          <div className="space-y-6">
            {/* Основная информация */}
            <div className="bg-white rounded-lg shadow p-6 space-y-4">
              <h2 className="text-lg font-semibold text-gray-800 border-b pb-2">📋 Основная информация</h2>
              <div className="flex flex-wrap gap-4">
                <Field label="Название" field="name" half />
                <Field label="Юридическое наименование" field="legal_name" half />
                <Field label="ИНН" field="inn" placeholder="10 или 12 цифр" half />
                <Field label="КПП" field="kpp" placeholder="9 цифр" half />
                <Field label="ОГРН / ОГРНИП" field="ogrn" placeholder="13 или 15 цифр" half />
                <Field label="ОКПО" field="okpo" placeholder="8 или 10 цифр" half />
              </div>
            </div>

            {/* Адреса */}
            <div className="bg-white rounded-lg shadow p-6 space-y-4">
              <h2 className="text-lg font-semibold text-gray-800 border-b pb-2">📍 Адреса</h2>
              <div className="space-y-4">
                <Field label="Юридический адрес" field="legal_address" placeholder="г. Москва, ул. ..." />
                <Field label="Фактический адрес" field="actual_address" placeholder="Совпадает с юридическим или другой" />
              </div>
            </div>

            {/* Контакты */}
            <div className="bg-white rounded-lg shadow p-6 space-y-4">
              <h2 className="text-lg font-semibold text-gray-800 border-b pb-2">📞 Контакты</h2>
              <div className="flex flex-wrap gap-4">
                <Field label="Телефон" field="phone" placeholder="+7 (999) 123-45-67" half />
                <Field label="Email для документов" field="email" placeholder="billing@company.ru" half />
              </div>
            </div>

            {/* Банковские реквизиты */}
            <div className="bg-white rounded-lg shadow p-6 space-y-4">
              <h2 className="text-lg font-semibold text-gray-800 border-b pb-2">🏦 Банковские реквизиты</h2>
              <div className="flex flex-wrap gap-4">
                <Field label="Наименование банка" field="bank_name" placeholder='ПАО "Сбербанк"' />
                <Field label="БИК" field="bik" placeholder="9 цифр" half />
                <Field label="Расчётный счёт" field="checking_account" placeholder="20 цифр" half />
                <Field label="Корреспондентский счёт" field="correspondent_account" placeholder="20 цифр" half />
              </div>
            </div>

            {/* Руководитель */}
            <div className="bg-white rounded-lg shadow p-6 space-y-4">
              <h2 className="text-lg font-semibold text-gray-800 border-b pb-2">👤 Руководитель</h2>
              <div className="flex flex-wrap gap-4">
                <Field label="ФИО руководителя" field="director_name" placeholder="Иванов Иван Иванович" half />
                <Field label="Должность" field="director_position" placeholder="Генеральный директор" half />
              </div>
            </div>

            {/* Кнопка сохранения реквизитов */}
            <div className="flex justify-end pt-2">
              <button
                onClick={handleSaveRequisites}
                disabled={savingRequisites}
                className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {savingRequisites ? '⏳ Сохранение...' : '💾 Сохранить реквизиты'}
              </button>
            </div>
          </div>
        )}

        {/* Вкладка: Налоги */}
        {activeTab === 'tax' && (
          <div className="bg-white rounded-lg shadow p-6 space-y-6">
            <div>
              <h2 className="text-lg font-semibold text-gray-900 mb-2">💼 Налоги и сборы</h2>
              <p className="text-sm text-gray-600 mb-4">
                Эти настройки будут использоваться по умолчанию при создании новых счетов и актов.
              </p>

              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <TaxSystemSelector
                  value={taxSettings.default_tax_system}
                  onChange={handleTaxSystemChange}
                  onVatRateChange={(rate) =>
                    setTaxSettings((prev) => ({ ...prev, default_vat_rate: parseFloat(rate) }))
                  }
                />

                {taxSettings.default_tax_system === 'osno' && (
                  <div className="mt-3 flex items-center">
                    <input
                      id="defaultVatIncluded"
                      type="checkbox"
                      checked={taxSettings.default_is_vat_included}
                      onChange={(e) =>
                        setTaxSettings((prev) => ({ ...prev, default_is_vat_included: e.target.checked }))
                      }
                      className="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500"
                    />
                    <label htmlFor="defaultVatIncluded" className="ml-2 text-sm text-gray-700">
                      НДС включён в сумму по умолчанию
                    </label>
                  </div>
                )}
              </div>
            </div>

            <div className="flex justify-end pt-4 border-t">
              <button
                onClick={handleSaveTax}
                disabled={saving}
                className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {saving ? '⏳ Сохранение...' : '💾 Сохранить налоговые настройки'}
              </button>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default CompanySettingsPage;