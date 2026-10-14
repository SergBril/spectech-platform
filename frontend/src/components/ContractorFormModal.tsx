import React, { useState, useEffect, useRef } from 'react';
import type { Contractor, ContractorCreate, ContractorUpdate, BankDetails } from '../api/contractors';

interface Props {
  contractor: Contractor | null;
  onClose: () => void;
  onSave: (data: ContractorCreate | ContractorUpdate) => Promise<void>;
}

const TAX_SYSTEMS = [
  { value: 'osno', label: 'ОСНО (с НДС)' },
  { value: 'usn_6', label: 'УСН Доходы (6%)' },
  { value: 'usn_15', label: 'УСН Доходы-Расходы (15%)' },
  { value: 'patent', label: 'Патент' },
  { value: 'npd', label: 'НПД / Самозанятый' },
];

const CONTRACTOR_TYPES = [
  { value: 'client', label: 'Клиент' },
  { value: 'owner', label: 'Собственник техники' },
  { value: 'subcontractor', label: 'Субподрядчик' },
];

// Компонент поля с DaData-подсказками (вынесен наружу для стабильности)
function DadataField({
  label,
  value,
  onChange,
  placeholder,
  required,
  queryType,
  onSuggestionSelect,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  required?: boolean;
  queryType: 'party' | 'address' | 'bank';
  onSuggestionSelect?: (s: any) => void;
}) {
  const [suggestions, setSuggestions] = useState<any[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleInput = (val: string) => {
    onChange(val);
    if (timerRef.current) clearTimeout(timerRef.current);
    if (val.length < 3) {
      setShowSuggestions(false);
      return;
    }
    timerRef.current = setTimeout(async () => {
      try {
        const token = localStorage.getItem('access_token');
        const apiUrl = import.meta.env.VITE_API_URL;
        const response = await fetch(`${apiUrl}/companies/dadata/suggest/${queryType}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({ query: val, count: 5 }),
        });
        const data = await response.json();
        if (data.suggestions?.length > 0) {
          setSuggestions(data.suggestions);
          setShowSuggestions(true);
        } else {
          setShowSuggestions(false);
        }
      } catch {
        setShowSuggestions(false);
      }
    }, 300);
  };

  return (
    <div className="relative">
      <label className="block text-sm font-medium text-gray-700 mb-1">
        {label}{required && ' *'}
      </label>
      <input
        type="text"
        value={value}
        onChange={(e) => handleInput(e.target.value)}
        onFocus={() => { if (suggestions.length > 0) setShowSuggestions(true); }}
        placeholder={placeholder}
        required={required}
        autoComplete="off"
        className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
      />
      {showSuggestions && suggestions.length > 0 && (
        <div className="absolute z-50 left-0 right-0 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-xl max-h-48 overflow-y-auto">
          {suggestions.map((s, i) => (
            <button
              key={i}
              type="button"
              onMouseDown={(e) => {
                e.preventDefault();
                onSuggestionSelect?.(s);
                setShowSuggestions(false);
                setSuggestions([]);
              }}
              className="w-full text-left px-3 py-2 text-sm hover:bg-blue-50 transition-colors border-b border-gray-100 last:border-0"
            >
              <div className="font-medium text-gray-900">{s.value}</div>
              {s.data?.inn && <div className="text-xs text-gray-500">ИНН: {s.data.inn}</div>}
              {s.data?.address?.value && s.data.address.value !== s.value && (
                <div className="text-xs text-gray-500 truncate">{s.data.address.value}</div>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export const ContractorFormModal: React.FC<Props> = ({ contractor, onClose, onSave }) => {
  const [activeTab, setActiveTab] = useState<'basic' | 'address' | 'bank' | 'contact' | 'tax'>('basic');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const [formData, setFormData] = useState({
    type: contractor?.type || 'client',
    name: contractor?.name || '',
    inn: contractor?.inn || '',
    kpp: contractor?.kpp || '',
    ogrn: contractor?.ogrn || '',
    legal_address: contractor?.legal_address || '',
    actual_address: contractor?.actual_address || '',
    contact_name: contractor?.contact_name || '',
    contact_phone: contractor?.contact_phone || '',
    contact_email: contractor?.contact_email || '',
    tax_system: contractor?.tax_system || 'osno',
  });

  const [bankDetails, setBankDetails] = useState<BankDetails>(
    contractor?.bank_details || {
      account: '',
      bank_name: '',
      bik: '',
      correspondent_account: '',
    }
  );

  // Обработчик автозаполнения из DaData (кнопка Найти в ЕГРЮЛ)
  const handleInnFound = (data: any) => {
    setFormData((prev) => ({
      ...prev,
      name: data.name || suggestion?.value || prev.name,
      inn: data.inn || prev.inn,
      kpp: data.kpp || prev.kpp,
      ogrn: data.ogrn || prev.ogrn,
      legal_address: data.address || prev.legal_address,
    }));
    if (data.bank_name || data.bank_bik || data.bank_account) {
      setBankDetails((prev) => ({
        ...prev,
        account: data.bank_account || prev.account,
        bank_name: data.bank_name || prev.bank_name,
        bik: data.bank_bik || prev.bik,
        correspondent_account: data.bank_correspondent_account || prev.correspondent_account,
      }));
    }
  };

  // Автозаполнение всех полей при выборе подсказки по названию
  const handleNameSuggestionSelect = (suggestion: any) => {
    const p = suggestion.data;
    setFormData((prev) => ({
      ...prev,
      name: p.name?.short_with_opf || suggestion.value,
      inn: p.inn || prev.inn,
      kpp: p.kpp || prev.kpp,
      ogrn: p.ogrn || prev.ogrn,
      legal_address: p.address?.value || prev.legal_address,
    }));
    if (p.finance?.bank_name || p.finance?.bank_bik) {
      setBankDetails((prev) => ({
        ...prev,
        bank_name: p.finance.bank_name || prev.bank_name,
        bik: p.finance.bank_bik || prev.bik,
        correspondent_account: p.finance.bank_correspondent_account || prev.correspondent_account,
      }));
    }
  };

  const handleDuplicateFound = (existingId: number, existingName: string) => {
    if (confirm(`Контрагент "${existingName}" уже существует. Закрыть форму?`)) {
      onClose();
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!formData.name.trim()) {
      setError('Название обязательно');
      return;
    }

    setSaving(true);
    try {
      await onSave({
        ...formData,
        bank_details: bankDetails,
      });
    } catch (err: any) {
      setError('Ошибка: ' + (err?.response?.data?.detail || err.message));
    } finally {
      setSaving(false);
    }
  };

  const tabs = [
    { id: 'basic', label: '📋 Основное', icon: '📋' },
    { id: 'address', label: '📍 Адреса', icon: '📍' },
    { id: 'bank', label: '🏦 Банк', icon: '🏦' },
    { id: 'contact', label: '👤 Контакты', icon: '👤' },
    { id: 'tax', label: '💼 Налоги', icon: '💼' },
  ];

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold text-gray-900">
              {contractor ? `Редактировать: ${contractor.name}` : 'Новый контрагент'}
            </h2>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl">
              ×
            </button>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
              {error}
            </div>
          )}

          {/* Tabs */}
          <div className="flex border-b border-gray-200 mb-6">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id as any)}
                className={`px-4 py-2 font-medium text-sm border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Tab: Основное */}
            {activeTab === 'basic' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Тип контрагента *
                  </label>
                  <select
                    value={formData.type}
                    onChange={(e) => setFormData({ ...formData, type: e.target.value as 'client' | 'owner' | 'subcontractor' })}
                    className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                  >
                    {CONTRACTOR_TYPES.map((type) => (
                      <option key={type.value} value={type.value}>
                        {type.label}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Название с DaData-подсказками */}
                <DadataField
                  label="Название"
                  value={formData.name}
                  onChange={(v) => setFormData({ ...formData, name: v })}
                  placeholder='ООО "Ромашка"'
                  required
                  queryType="party"
                  onSuggestionSelect={handleNameSuggestionSelect}
                />

                {/* ИНН с DaData-подсказками */}
                <DadataField
                  label="ИНН"
                  value={formData.inn}
                  onChange={(v) => setFormData((prev) => ({ ...prev, inn: v.replace(/\D/g, '').slice(0, 12) }))}
                  placeholder="7707083893"
                  queryType="party"
                  onSuggestionSelect={handleNameSuggestionSelect}
                />

                {/* КПП и ОГРН в гриде */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">КПП</label>
                    <input
                      type="text"
                      value={formData.kpp}
                      onChange={(e) => setFormData({ ...formData, kpp: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                      placeholder="771201001"
                      maxLength={9}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">ОГРН</label>
                    <input
                      type="text"
                      value={formData.ogrn}
                      onChange={(e) => setFormData({ ...formData, ogrn: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                      placeholder="1027700123456"
                      maxLength={15}
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Tab: Адреса */}
            {activeTab === 'address' && (
              <div className="space-y-4">
                <DadataField
                  label="Юридический адрес"
                  value={formData.legal_address}
                  onChange={(v) => setFormData({ ...formData, legal_address: v })}
                  placeholder="123456, г. Москва, ул. Ленина, д. 10, оф. 5"
                  queryType="address"
                  onSuggestionSelect={(s) => setFormData((prev) => ({ ...prev, legal_address: s.value }))}
                />

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Фактический адрес
                  </label>
                  <textarea
                    value={formData.actual_address}
                    onChange={(e) => setFormData({ ...formData, actual_address: e.target.value })}
                    rows={3}
                    className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                    placeholder="Если отличается от юридического"
                  />
                </div>
              </div>
            )}

            {/* Tab: Банк */}
            {activeTab === 'bank' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Расчётный счёт
                  </label>
                  <input
                    type="text"
                    value={bankDetails.account || ''}
                    onChange={(e) => setBankDetails({ ...bankDetails, account: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                    placeholder="40702810400000012345"
                    maxLength={20}
                  />
                </div>

                <DadataField
                  label="Наименование банка"
                  value={bankDetails.bank_name || ''}
                  onChange={(v) => setBankDetails({ ...bankDetails, bank_name: v })}
                  placeholder='ПАО "Сбербанк"'
                  queryType="bank"
                  onSuggestionSelect={(s) => {
                    const b = s.data;
                    setBankDetails((prev) => ({
                      ...prev,
                      bank_name: b.name?.payment || s.value,
                      bik: b.bic || prev.bik,
                      correspondent_account: b.accounts?.[0]?.ks || prev.correspondent_account,
                    }));
                  }}
                />

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">БИК</label>
                    <input
                      type="text"
                      value={bankDetails.bik || ''}
                      onChange={(e) => setBankDetails({ ...bankDetails, bik: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                      placeholder="044525225"
                      maxLength={9}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Корр. счёт
                    </label>
                    <input
                      type="text"
                      value={bankDetails.correspondent_account || ''}
                      onChange={(e) =>
                        setBankDetails({ ...bankDetails, correspondent_account: e.target.value })
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                      placeholder="30101810400000000225"
                      maxLength={20}
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Tab: Контакты */}
            {activeTab === 'contact' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Контактное лицо
                  </label>
                  <input
                    type="text"
                    value={formData.contact_name}
                    onChange={(e) => setFormData({ ...formData, contact_name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                    placeholder="Иванов Иван Иванович"
                  />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Телефон</label>
                    <input
                      type="tel"
                      value={formData.contact_phone}
                      onChange={(e) => setFormData({ ...formData, contact_phone: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                      placeholder="+7 (999) 123-45-67"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                    <input
                      type="email"
                      value={formData.contact_email}
                      onChange={(e) => setFormData({ ...formData, contact_email: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                      placeholder="client@example.com"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Tab: Налоги */}
            {activeTab === 'tax' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Система налогообложения
                  </label>
                  <select
                    value={formData.tax_system}
                    onChange={(e) => setFormData({ ...formData, tax_system: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                  >
                    {TAX_SYSTEMS.map((system) => (
                      <option key={system.value} value={system.value}>
                        {system.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="bg-blue-50 border border-blue-200 rounded p-4 text-sm text-blue-800">
                  💡 Система налогообложения клиента влияет на корректное указание НДС в документах.
                  Для клиентов на УСН/Патент/НПД в счетах будет указано "Без НДС".
                </div>
              </div>
            )}

            {/* Buttons */}
            <div className="flex justify-end space-x-3 pt-4 border-t">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 border border-gray-300 text-gray-700 rounded hover:bg-gray-50"
                disabled={saving}
              >
                Отмена
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                disabled={saving}
              >
                {saving ? 'Сохранение...' : contractor ? 'Сохранить' : 'Создать'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default ContractorFormModal;