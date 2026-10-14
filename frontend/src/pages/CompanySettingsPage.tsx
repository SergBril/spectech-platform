import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useCompany } from '../contexts/CompanyContext';
import { companiesApi, type CompanyTaxSettings } from '../api/companies';
import { TaxSystemSelector } from '../components/TaxSystemSelector';
import { showToast } from '../utils/toast';
import apiClient from '../api/client';
import Layout from '../components/Layout';

const DADATA_API_KEY = import.meta.env.VITE_DADATA_API_KEY || '';

// Вынесен наружу чтобы не пересоздавался при рендере
function RequisiteField({
  label,
  value,
  onChange,
  placeholder,
  half,
  onDadataInput,
  suggestions,
  showSuggestions,
  onSelectSuggestion,
  isActive,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  half?: boolean;
  onDadataInput?: (v: string) => void;
  suggestions?: any[];
  showSuggestions?: boolean;
  onSelectSuggestion?: (s: any) => void;
  isActive?: boolean;
}) {
  const wrapperRef = useRef<HTMLDivElement>(null);

  return (
    <div ref={wrapperRef} className={`${half ? 'flex-1 min-w-[250px]' : 'w-full'} relative`}>
      <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
      <input
        type="text"
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
          onDadataInput?.(e.target.value);
        }}
        placeholder={placeholder}
        autoComplete="off"
        className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none transition-shadow"
      />
      {showSuggestions && isActive && suggestions && suggestions.length > 0 && (
        <div className="absolute z-50 left-0 right-0 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-xl max-h-48 overflow-y-auto">
          {suggestions.map((s, i) => (
            <button
              key={i}
              onMouseDown={(e) => {
                e.preventDefault(); // предотвращает потерю фокуса input
                onSelectSuggestion?.(s);
              }}
              className="w-full text-left px-3 py-2 text-sm hover:bg-blue-50 transition-colors border-b border-gray-100 last:border-0"
            >
              <div className="font-medium text-gray-900">{s.value}</div>
              {s.data?.inn && <div className="text-xs text-gray-500">ИНН: {s.data.inn}</div>}
              {s.data?.address?.value && s.data.address.value !== s.value && (
                <div className="text-xs text-gray-500">{s.data.address.value}</div>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export const CompanySettingsPage: React.FC = () => {
  const { currentCompany, currentCompanyId } = useCompany();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savingRequisites, setSavingRequisites] = useState(false);
  const [activeTab, setActiveTab] = useState<'requisites' | 'tax'>('requisites');

  const [taxSettings, setTaxSettings] = useState<CompanyTaxSettings>({
    default_tax_system: 'osno',
    default_vat_rate: 20,
    default_is_vat_included: true,
  });

  const [requisites, setRequisites] = useState({
    name: '', legal_name: '', inn: '', kpp: '', ogrn: '', okpo: '',
    legal_address: '', actual_address: '', phone: '', email: '',
    bank_name: '', bik: '', checking_account: '', correspondent_account: '',
    director_name: '', director_position: '',
  });

  const initializedRef = useRef<string | null>(null);

  // DaData state
  const [dadataSuggestions, setDadataSuggestions] = useState<any[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [activeDadataField, setActiveDadataField] = useState<string | null>(null);
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
          name: c.name || '', legal_name: c.legal_name || '',
          inn: c.inn || '', kpp: c.kpp || '', ogrn: c.ogrn || '', okpo: c.okpo || '',
          legal_address: c.legal_address || '', actual_address: c.actual_address || '',
          phone: c.phone || '', email: c.email || '',
          bank_name: c.bank_name || '', bik: c.bik || '',
          checking_account: c.checking_account || '', correspondent_account: c.correspondent_account || '',
          director_name: c.director_name || '', director_position: c.director_position || '',
        });
        initializedRef.current = String(currentCompanyId);
      }
    } catch {
      showToast.error('Не удалось загрузить настройки');
    } finally {
      setLoading(false);
    }
  }, [currentCompanyId, currentCompany]);

  useEffect(() => { loadData(); }, [loadData]);

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

  const handleDadataInput = (field: string, value: string) => {
    setActiveDadataField(field);
    if (!DADATA_API_KEY || value.length < 3) {
      setShowSuggestions(false);
      return;
    }
    if (dadataTimerRef.current) clearTimeout(dadataTimerRef.current);
    dadataTimerRef.current = setTimeout(async () => {
      try {
        let queryType = 'address';
        if (field === 'bank_name' || field === 'bik') queryType = 'bank';
        if (field === 'inn' || field === 'ogrn' || field === 'name' || field === 'legal_name') queryType = 'party';

        const response = await fetch(`${import.meta.env.VITE_API_URL}/companies/dadata/suggest/${queryType}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(localStorage.getItem('access_token')
              ? { Authorization: `Bearer ${localStorage.getItem('access_token')}` }
              : {}),
          },
          body: JSON.stringify({ query: value, count: 5 }),
        });
        const data = await response.json();
        if (data.suggestions?.length > 0) {
          setDadataSuggestions(data.suggestions);
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
    const field = activeDadataField;
    if (!field) return;

    if (['inn', 'ogrn', 'name', 'legal_name'].includes(field)) {
      const p = suggestion.data;
      setRequisites((prev) => ({
        ...prev,
        inn: p.inn || prev.inn,
        kpp: p.kpp || prev.kpp,
        ogrn: p.ogrn || prev.ogrn,
        legal_name: p.name?.full_with_opf || prev.legal_name,
        name: p.name?.short_with_opf || prev.name,
        legal_address: p.address?.value || prev.legal_address,
        director_name: p.management?.name || prev.director_name,
        director_position: p.management?.post || prev.director_position,
      }));
    } else if (field === 'bank_name' || field === 'bik') {
      const b = suggestion.data;
      setRequisites((prev) => ({
        ...prev,
        bank_name: b.name?.payment || prev.bank_name,
        bik: b.bic || prev.bik,
        correspondent_account: b.accounts?.[0]?.ks || prev.correspondent_account,
      }));
    } else {
      setRequisites((prev) => ({
        ...prev,
        [field]: suggestion.value || suggestion.data?.value || prev[field as keyof typeof prev],
      }));
    }
    setShowSuggestions(false);
    setDadataSuggestions([]);
    setActiveDadataField(null);
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

  const tabs = [
    { id: 'requisites' as const, label: '📄 Реквизиты' },
    { id: 'tax' as const, label: '💼 Налоги' },
  ];

  const dadataFields = ['name', 'legal_name', 'inn', 'ogrn', 'legal_address', 'actual_address', 'bank_name', 'bik', 'director_name'];

  return (
    <Layout>
      <div className="p-6 max-w-4xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">⚙️ Настройки компании</h1>
          <span className="text-sm text-gray-500 bg-gray-100 px-3 py-1 rounded-full">
            {currentCompany?.name}
          </span>
        </div>

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

        {activeTab === 'requisites' && (
          <div className="space-y-6">
            <div className="bg-white rounded-lg shadow p-6 space-y-4">
              <h2 className="text-lg font-semibold text-gray-800 border-b pb-2">📋 Основная информация</h2>
              <div className="flex flex-wrap gap-4">
                <RequisiteField label="Название" value={requisites.name} onChange={(v) => handleRequisiteChange('name', v)} half
                  onDadataInput={(v) => handleDadataInput('name', v)} suggestions={dadataSuggestions} showSuggestions={showSuggestions}
                  onSelectSuggestion={applyDadataSuggestion} isActive={activeDadataField === 'name'} />
                <RequisiteField label="Юридическое наименование" value={requisites.legal_name} onChange={(v) => handleRequisiteChange('legal_name', v)} half
                  onDadataInput={(v) => handleDadataInput('legal_name', v)} suggestions={dadataSuggestions} showSuggestions={showSuggestions}
                  onSelectSuggestion={applyDadataSuggestion} isActive={activeDadataField === 'legal_name'} />
                <RequisiteField label="ИНН" value={requisites.inn} onChange={(v) => handleRequisiteChange('inn', v)} placeholder="10 или 12 цифр" half
                  onDadataInput={(v) => handleDadataInput('inn', v)} suggestions={dadataSuggestions} showSuggestions={showSuggestions}
                  onSelectSuggestion={applyDadataSuggestion} isActive={activeDadataField === 'inn'} />
                <RequisiteField label="КПП" value={requisites.kpp} onChange={(v) => handleRequisiteChange('kpp', v)} placeholder="9 цифр" half />
                <RequisiteField label="ОГРН / ОГРНИП" value={requisites.ogrn} onChange={(v) => handleRequisiteChange('ogrn', v)} placeholder="13 или 15 цифр" half
                  onDadataInput={(v) => handleDadataInput('ogrn', v)} suggestions={dadataSuggestions} showSuggestions={showSuggestions}
                  onSelectSuggestion={applyDadataSuggestion} isActive={activeDadataField === 'ogrn'} />
                <RequisiteField label="ОКПО" value={requisites.okpo} onChange={(v) => handleRequisiteChange('okpo', v)} placeholder="8 или 10 цифр" half />
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6 space-y-4">
              <h2 className="text-lg font-semibold text-gray-800 border-b pb-2">📍 Адреса</h2>
              <div className="space-y-4">
                <RequisiteField label="Юридический адрес" value={requisites.legal_address} onChange={(v) => handleRequisiteChange('legal_address', v)} placeholder="г. Москва, ул. ..."
                  onDadataInput={(v) => handleDadataInput('legal_address', v)} suggestions={dadataSuggestions} showSuggestions={showSuggestions}
                  onSelectSuggestion={applyDadataSuggestion} isActive={activeDadataField === 'legal_address'} />
                <RequisiteField label="Фактический адрес" value={requisites.actual_address} onChange={(v) => handleRequisiteChange('actual_address', v)} placeholder="Совпадает с юридическим или другой"
                  onDadataInput={(v) => handleDadataInput('actual_address', v)} suggestions={dadataSuggestions} showSuggestions={showSuggestions}
                  onSelectSuggestion={applyDadataSuggestion} isActive={activeDadataField === 'actual_address'} />
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6 space-y-4">
              <h2 className="text-lg font-semibold text-gray-800 border-b pb-2">📞 Контакты</h2>
              <div className="flex flex-wrap gap-4">
                <RequisiteField label="Телефон" value={requisites.phone} onChange={(v) => handleRequisiteChange('phone', v)} placeholder="+7 (999) 123-45-67" half />
                <RequisiteField label="Email для документов" value={requisites.email} onChange={(v) => handleRequisiteChange('email', v)} placeholder="billing@company.ru" half />
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6 space-y-4">
              <h2 className="text-lg font-semibold text-gray-800 border-b pb-2">🏦 Банковские реквизиты</h2>
              <div className="flex flex-wrap gap-4">
                <RequisiteField label="Наименование банка" value={requisites.bank_name} onChange={(v) => handleRequisiteChange('bank_name', v)} placeholder='ПАО "Сбербанк"'
                  onDadataInput={(v) => handleDadataInput('bank_name', v)} suggestions={dadataSuggestions} showSuggestions={showSuggestions}
                  onSelectSuggestion={applyDadataSuggestion} isActive={activeDadataField === 'bank_name'} />
                <RequisiteField label="БИК" value={requisites.bik} onChange={(v) => handleRequisiteChange('bik', v)} placeholder="9 цифр" half
                  onDadataInput={(v) => handleDadataInput('bik', v)} suggestions={dadataSuggestions} showSuggestions={showSuggestions}
                  onSelectSuggestion={applyDadataSuggestion} isActive={activeDadataField === 'bik'} />
                <RequisiteField label="Расчётный счёт" value={requisites.checking_account} onChange={(v) => handleRequisiteChange('checking_account', v)} placeholder="20 цифр" half />
                <RequisiteField label="Корреспондентский счёт" value={requisites.correspondent_account} onChange={(v) => handleRequisiteChange('correspondent_account', v)} placeholder="20 цифр" half />
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6 space-y-4">
              <h2 className="text-lg font-semibold text-gray-800 border-b pb-2">👤 Руководитель</h2>
              <div className="flex flex-wrap gap-4">
                <RequisiteField label="ФИО руководителя" value={requisites.director_name} onChange={(v) => handleRequisiteChange('director_name', v)} placeholder="Иванов Иван Иванович" half
                  onDadataInput={(v) => handleDadataInput('director_name', v)} suggestions={dadataSuggestions} showSuggestions={showSuggestions}
                  onSelectSuggestion={applyDadataSuggestion} isActive={activeDadataField === 'director_name'} />
                <RequisiteField label="Должность" value={requisites.director_position} onChange={(v) => handleRequisiteChange('director_position', v)} placeholder="Генеральный директор" half />
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button onClick={handleSaveRequisites} disabled={savingRequisites}
                className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors">
                {savingRequisites ? '⏳ Сохранение...' : '💾 Сохранить реквизиты'}
              </button>
            </div>
          </div>
        )}

        {activeTab === 'tax' && (
          <div className="bg-white rounded-lg shadow p-6 space-y-6">
            <div>
              <h2 className="text-lg font-semibold text-gray-900 mb-2">💼 Налоги и сборы</h2>
              <p className="text-sm text-gray-600 mb-4">Эти настройки будут использоваться по умолчанию при создании новых счетов и актов.</p>
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <TaxSystemSelector value={taxSettings.default_tax_system} onChange={handleTaxSystemChange}
                  onVatRateChange={(rate) => setTaxSettings((prev) => ({ ...prev, default_vat_rate: parseFloat(rate) }))} />
                {taxSettings.default_tax_system === 'osno' && (
                  <div className="mt-3 flex items-center">
                    <input id="defaultVatIncluded" type="checkbox" checked={taxSettings.default_is_vat_included}
                      onChange={(e) => setTaxSettings((prev) => ({ ...prev, default_is_vat_included: e.target.checked }))}
                      className="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500" />
                    <label htmlFor="defaultVatIncluded" className="ml-2 text-sm text-gray-700">НДС включён в сумму по умолчанию</label>
                  </div>
                )}
              </div>
            </div>
            <div className="flex justify-end pt-4 border-t">
              <button onClick={handleSaveTax} disabled={saving}
                className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors">
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