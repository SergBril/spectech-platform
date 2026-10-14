import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useCompany } from '../contexts/CompanyContext';
import { companiesApi, type CompanyTaxSettings } from '../api/companies';
import { TaxSystemSelector } from '../components/TaxSystemSelector';
import { showToast } from '../utils/toast';
import apiClient from '../api/client';
import Layout from '../components/Layout';

const DADATA_API_KEY = import.meta.env.VITE_DADATA_API_KEY || '';

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

  // Ref для предотвращения перезаполнения формы при каждом рендере
  const initializedRef = useRef<string | null>(null);

  // Dadata suggestions
  const [dadataSuggestions, setDadataSuggestions] = useState<any[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [dadataField, setDadataField] = useState<string | null>(null);
  const suggestionsRef = useRef<HTMLDivElement>(null);
  const dadataTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadData = useCallback(async () => {
    if (!currentCompanyId) return;
    try {
      setLoading(true);
      const taxData = await companiesApi.getTaxSettings(currentCompanyId);
      setTaxSettings(taxData);

      if (currentCompany && initializedRef.current !== String(currentCompanyId)) {
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
        initializedRef.current = String(currentCompanyId);
      }
    } catch (err: any) {
      showToast.error('Не удалось загрузить настройки');
    } finally {
      setLoading(false);
    }
  }, [currentCompanyId, currentCompany]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Закрытие подсказок при клике вне
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (suggestionsRef.current && !suggestionsRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

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

  // Dadata autocomplete
  const handleDadataInput = (field: string, value: string) => {
    handleRequisiteChange(field, value);

    if (!DADATA_API_KEY || value.length < 3) {
      setShowSuggestions(false);
      return;
    }

    // Debounce
    if (dadataTimerRef.current) clearTimeout(dadataTimerRef.current);

    dadataTimerRef.current = setTimeout(async () => {
      try {
        let queryType = 'address';
        if (field === 'bank_name' || field === 'bik') queryType = 'bank';
        if (field === 'inn' || field === 'ogrn') queryType = 'party';

        const response = await fetch(`https://suggestions.dadata.ru/suggestion/api/4_1/rs/suggest/${queryType}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'application/json',
            Authorization: `Token ${DADATA_API_KEY}`,
          },
          body: JSON.stringify({ query: value, count: 5 }),
        });

        const data = await response.json();
        if (data.suggestions && data.suggestions.length > 0) {
          setDadataSuggestions(data.suggestions);
          setDadataField(field);
          setShowSuggestions(true);
        } else {
          setShowSuggestions(false);
        }
      } catch {
        setShowSuggestions(false);
      }
    }, 300);
  };

  const applyDadataSuggestion = (suggestion: any) => {
    const field = dadataField;
    if (!field) return;

    if (field === 'inn' || field === 'ogrn') {
      // Party suggestion
      const party = suggestion.data;
      setRequisites((prev) => ({
        ...prev,
        inn: party.inn || prev.inn,
        kpp: party.kpp || prev.kpp,
        ogrn: party.ogrn || prev.ogrn,
        legal_name: party.name?.full_with_opf || prev.legal_name,
        name: party.name?.short_with_opf || prev.name,
        legal_address: party.address?.value || prev.legal_address,
        director_name: party.management?.name || prev.director_name,
        director_position: party.management?.post || prev.director_position,
      }));
    } else if (field === 'bank_name' || field === 'bik') {
      // Bank suggestion
      const bank = suggestion.data;
      setRequisites((prev) => ({
        ...prev,
        bank_name: bank.name?.payment || prev.bank_name,
        bik: bank.bic || prev.bik,
        checking_account: bank.accounts?.[0]?.ks || prev.checking_account,
        correspondent_account: bank.accounts?.[0]?.ks || prev.correspondent_account,
      }));
    } else {
      // Address or plain text
      setRequisites((prev) => ({
        ...prev,
        [field]: suggestion.value || suggestion.data?.value || prev[field as keyof typeof prev],
      }));
    }

    setShowSuggestions(false);
    setDadataSuggestions([]);
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

  const Field = ({ label, field, placeholder, half, dadata }: { label: string; field: string; placeholder?: string; half?: boolean; dadata?: boolean }) => (
    <div className={`${half ? 'flex-1 min-w-[250px]' : 'w-full'} relative`}>
      <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
      <input
        type="text"
        value={requisites[field as keyof typeof requisites]}
        onChange={(e) => dadata ? handleDadataInput(field, e.target.value) : handleRequisiteChange(field, e.target.value)}
        onFocus={() => { if (dadata && dadataSuggestions.length > 0 && dadataField === field) setShowSuggestions(true); }}
        placeholder={placeholder}
        autoComplete="off"
        className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none transition-shadow"
      />
      {dadata && showSuggestions && dadataField === field && dadataSuggestions.length > 0 && (
        <div
          ref={suggestionsRef}
          className="absolute z-50 left-0 right-0 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-xl max-h-48 overflow-y-auto"
        >
          {dadataSuggestions.map((s, i) => (
            <button
              key={i}
              onClick={() => applyDadataSuggestion(s)}
              className="w-full text-left px-3 py-2 text-sm hover:bg-blue-50 transition-colors border-b border-gray-100 last:border-0"
            >
              <div className="font-medium text-gray-900">{s.value}</div>
              {s.data?.address?.value && s.data.address.value !== s.value && (
                <div className="text-xs text-gray-500">{s.data.address.value}</div>
              )}
              {s.data?.inn && (
                <div className="text-xs text-gray-500">ИНН: {s.data.inn}</div>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );

  const tabs = [
    { id: 'requisites' as const, label: '📄 Реквизиты' },
    { id: 'tax' as const, label: '💼 Налоги' },
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
                <Field label="Название" field="name" half dadata />
                <Field label="Юридическое наименование" field="legal_name" half dadata />
                <Field label="ИНН" field="inn" placeholder="10 или 12 цифр" half dadata />
                <Field label="КПП" field="kpp" placeholder="9 цифр" half />
                <Field label="ОГРН / ОГРНИП" field="ogrn" placeholder="13 или 15 цифр" half dadata />
                <Field label="ОКПО" field="okpo" placeholder="8 или 10 цифр" half />
              </div>
            </div>

            {/* Адреса */}
            <div className="bg-white rounded-lg shadow p-6 space-y-4">
              <h2 className="text-lg font-semibold text-gray-800 border-b pb-2">📍 Адреса</h2>
              <div className="space-y-4">
                <Field label="Юридический адрес" field="legal_address" placeholder="г. Москва, ул. ..." dadata />
                <Field label="Фактический адрес" field="actual_address" placeholder="Совпадает с юридическим или другой" dadata />
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
                <Field label="Наименование банка" field="bank_name" placeholder='ПАО "Сбербанк"' dadata />
                <Field label="БИК" field="bik" placeholder="9 цифр" half dadata />
                <Field label="Расчётный счёт" field="checking_account" placeholder="20 цифр" half />
                <Field label="Корреспондентский счёт" field="correspondent_account" placeholder="20 цифр" half />
              </div>
            </div>

            {/* Руководитель */}
            <div className="bg-white rounded-lg shadow p-6 space-y-4">
              <h2 className="text-lg font-semibold text-gray-800 border-b pb-2">👤 Руководитель</h2>
              <div className="flex flex-wrap gap-4">
                <Field label="ФИО руководителя" field="director_name" placeholder="Иванов Иван Иванович" half dadata />
                <Field label="Должность" field="director_position" placeholder="Генеральный директор" half />
              </div>
            </div>

            {/* Кнопка сохранения */}
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