import React, { useState } from 'react';

interface TaxSystemSelectorProps {
  value: string;
  onChange: (system: string) => void;
  onVatRateChange?: (vatRate: string) => void;
  disabled?: boolean;
}

// 📋 Захардкоженные значения (всегда доступны, не зависят от API)
const TAX_SYSTEMS = [
  { value: 'osno', label: 'ОСНО (с НДС)', has_vat: true },
  { value: 'usn_6', label: 'УСН Доходы (6%)', has_vat: false },
  { value: 'usn_15', label: 'УСН Доходы-Расходы (15%)', has_vat: false },
  { value: 'patent', label: 'Патент', has_vat: false },
  { value: 'npd', label: 'НПД / Самозанятый', has_vat: false },
];

const VAT_RATES = [
  { value: '0', label: 'Без НДС' },
  { value: '5', label: '5%' },
  { value: '7', label: '7%' },
  { value: '10', label: '10%' },
  { value: '20', label: '20%' },
  { value: '22', label: '22%' },
];

export const TaxSystemSelector: React.FC<TaxSystemSelectorProps> = ({
  value,
  onChange,
  onVatRateChange,
  disabled = false,
}) => {
  const [selectedVatRate, setSelectedVatRate] = useState('20');

  const handleSystemChange = (newSystem: string) => {
    onChange(newSystem);
    const system = TAX_SYSTEMS.find((s) => s.value === newSystem);

    if (system && !system.has_vat) {
      setSelectedVatRate('0');
      onVatRateChange?.('0');
    } else if (system?.has_vat && selectedVatRate === '0') {
      setSelectedVatRate('20');
      onVatRateChange?.('20');
    }
  };

  const handleVatRateChange = (newRate: string) => {
    setSelectedVatRate(newRate);
    onVatRateChange?.(newRate);
  };

  const currentSystem = TAX_SYSTEMS.find((s) => s.value === value);
  const showVatRateSelector = currentSystem?.has_vat ?? true;

  return (
    <div className="space-y-3">
      {/* Система налогообложения */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          💼 Система налогообложения
        </label>
        <select
          value={value}
          onChange={(e) => handleSystemChange(e.target.value)}
          disabled={disabled}
          className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none disabled:bg-gray-100"
        >
          {TAX_SYSTEMS.map((system) => (
            <option key={system.value} value={system.value}>
              {system.label}
            </option>
          ))}
        </select>
      </div>

      {/* Ставка НДС (только для ОСНО) */}
      {showVatRateSelector && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            🧾 Ставка НДС
          </label>
          <select
            value={selectedVatRate}
            onChange={(e) => handleVatRateChange(e.target.value)}
            disabled={disabled}
            className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none disabled:bg-gray-100"
          >
            {VAT_RATES.map((rate) => (
              <option key={rate.value} value={rate.value}>
                {rate.label}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Информационная подсказка для не-ОСНО систем */}
      {!showVatRateSelector && (
        <div className="bg-blue-50 border border-blue-200 rounded p-3 text-sm text-blue-800">
          💡 При данной системе налогообложения НДС не начисляется.
          В документе будет указано "Без НДС".
        </div>
      )}
    </div>
  );
};

export default TaxSystemSelector;
