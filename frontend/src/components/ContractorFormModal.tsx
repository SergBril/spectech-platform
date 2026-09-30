import React, { useState, useEffect } from 'react';
import type { Contractor, ContractorCreate, ContractorUpdate, BankDetails } from '../api/contractors';
import { InnSearchInput } from './InnSearchInput';

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
  // 🆕 Обработчик автозаполнения из DaData
  const handleInnFound = (data: any) => {
    setFormData({
      ...formData,
      name: data.name || formData.name,
      inn: data.inn || formData.inn,
      kpp: data.kpp || formData.kpp,
      ogrn: data.ogrn || formData.ogrn,
      legal_address: data.address || formData.legal_address,
    });

    // Заполняем банковские реквизиты, если они пришли
    if (data.bank_name || data.bank_bik || data.bank_account) {
      setBankDetails({
        account: data.bank_account || bankDetails.account,
        bank_name: data.bank_name || bankDetails.bank_name,
        bik: data.bank_bik || bankDetails.bik,
        correspondent_account: data.bank_correspondent_account || bankDetails.correspondent_account,
      });
    }
  };

  // 🆕 Обработчик найденного дубликата
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

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Название *
                  </label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                    placeholder='ООО "Ромашка"'
                    required
                  />
                </div>

                {/* 🆕 ИНН с поиском на отдельной строке */}
                <InnSearchInput
                  inn={formData.inn}
                  onInnChange={(inn) => setFormData({ ...formData, inn })}
                  onFound={handleInnFound}
                  onDuplicateFound={handleDuplicateFound}
                  disabled={!!contractor}
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
                </div>              </div>
            )}

            {/* Tab: Адреса */}
            {activeTab === 'address' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Юридический адрес
                  </label>
                  <textarea
                    value={formData.legal_address}
                    onChange={(e) => setFormData({ ...formData, legal_address: e.target.value })}
                    rows={3}
                    className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                    placeholder="123456, г. Москва, ул. Ленина, д. 10, оф. 5"
                  />
                </div>

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

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Название банка
                  </label>
                  <input
                    type="text"
                    value={bankDetails.bank_name || ''}
                    onChange={(e) => setBankDetails({ ...bankDetails, bank_name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                    placeholder='ПАО "Сбербанк"'
                  />
                </div>

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
