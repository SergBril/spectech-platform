import React, { useEffect, useState } from 'react';
import { taxApi } from '../api/finance';

interface TaxSystemSelectorProps {
  value: string;
  onChange: (system: string) => void;
  onVatRateChange?: (vatRate: string) => void;
  disabled?: boolean;
}

export const TaxSystemSelector: React.FC<TaxSystemSelectorProps> = ({
  value,
  onChange,
  onVatRateChange,
  disabled = false,
}) => {
  const [systems, setSystems] = useState<Array<{ value: string; label: string; has_vat: boolean }>>([]);
  const [vatRates, setVatRates] = useState<Array<{ value: string; label: string }>>([]);
  const [selectedVatRate, setSelectedVatRate] = useState('20');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      setLoading(true);
      const config = await taxApi.getConfig();
      setSystems(config.systems);
      setVatRates(config.vat_rates);
      setSelectedVatRate(config.default_vat_rate);
    } catch (error) {
      console.error('Failed to load tax config:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSystemChange = (newSystem: string) => {
    onChange(newSystem);
    const system = systems.find((s) => s.value === newSystem);

    // Если система без НДС — автоматически ставим 0%
    if (system && !system.has_vat) {
      setSelectedVatRate('0');
      onVatRateChange?.('0');
    }
    // Если это ОСНО и ставка была 0 — ставим 20%
    else if (system?.has_vat && selectedVatRate === '0') {
      setSelectedVatRate('20');
      onVatRateChange?.('20');
    }
  };

  const handleVatRateChange = (newRate: string) => {
    setSelectedVatRate(newRate);
    onVatRateChange?.(newRate);
  };

  const currentSystem = systems.find((s) => s.value === value);
  const showVatRateSelector = currentSystem?.has_vat ?? true;

  if (loading) {
    return <div className="text-gray-500 text-sm">Загрузка...</div>;
  }

  return (
    <div className="space-y-3">
      {/* Система налогообложения */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Система налогообложения
        </label>
        <select
          value={value}
          onChange={(e) => handleSystemChange(e.target.value)}
          disabled={disabled}
          className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none disabled:bg-gray-100"
        >
          {systems.map((system) => (
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
            Ставка НДС
          </label>
          <select
            value={selectedVatRate}
            onChange={(e) => handleVatRateChange(e.target.value)}
            disabled={disabled}
            className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none disabled:bg-gray-100"
          >
            {vatRates.map((rate) => (
              <option key={rate.value} value={rate.value}>
                {rate.label}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Подсказка для не-ОСНО систем */}
      {!showVatRateSelector && (
        <div className="bg-blue-50 border border-blue-200 rounded p-3 text-sm text-blue-800">
          💡 При данной системе налогообложения НДС не начисляется.
          В счёте будет указано "Без НДС".
        </div>
      )}
    </div>
  );
};
