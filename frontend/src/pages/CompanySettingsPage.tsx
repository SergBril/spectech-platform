import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { companiesApi, type CompanyTaxSettings } from '../api/companies';
import { TaxSystemSelector } from '../components/TaxSystemSelector';
import { showToast } from '../utils/toast';
import Navbar from '../components/Navbar';

export const CompanySettingsPage: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const companyId = user?.company_id || 1;

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [settings, setSettings] = useState<CompanyTaxSettings>({
    default_tax_system: 'osno',
    default_vat_rate: 20,
    default_is_vat_included: true,
  });

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      setLoading(true);
      const data = await companiesApi.getTaxSettings(companyId);
      setSettings(data);
    } catch (err: any) {
      showToast.error('Не удалось загрузить настройки');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      await companiesApi.updateTaxSettings(companyId, settings);
      showToast.success('Настройки сохранены');
    } catch (err: any) {
      showToast.error('Ошибка: ' + (err?.response?.data?.detail || err.message));
    } finally {
      setSaving(false);
    }
  };

  const handleTaxSystemChange = (newSystem: string) => {
    setSettings((prev) => ({
      ...prev,
      default_tax_system: newSystem,
      default_vat_rate: newSystem !== 'osno' ? 0 : prev.default_vat_rate === 0 ? 20 : prev.default_vat_rate,
    }));
  };

  if (loading) {
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
          <h1 className="text-2xl font-bold text-gray-900 mb-6">⚙️ Настройки компании</h1>

          <div className="space-y-6">
            <div>
              <h2 className="text-lg font-semibold text-gray-900 mb-4">💼 Налоги и сборы</h2>
              <p className="text-sm text-gray-600 mb-4">
                Эти настройки будут использоваться по умолчанию при создании новых счетов и актов.
              </p>

              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <TaxSystemSelector
                  value={settings.default_tax_system}
                  onChange={handleTaxSystemChange}
                  onVatRateChange={(rate) =>
                    setSettings((prev) => ({ ...prev, default_vat_rate: parseFloat(rate) }))
                  }
                />

                {settings.default_tax_system === 'osno' && (
                  <div className="mt-3 flex items-center">
                    <input
                      id="defaultVatIncluded"
                      type="checkbox"
                      checked={settings.default_is_vat_included}
                      onChange={(e) =>
                        setSettings((prev) => ({ ...prev, default_is_vat_included: e.target.checked }))
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

            <div className="flex justify-end space-x-3 pt-4 border-t">
              <button
                onClick={() => navigate('/')}
                className="px-4 py-2 border border-gray-300 text-gray-700 rounded hover:bg-gray-50"
                disabled={saving}
              >
                Отмена
              </button>
              <button
                onClick={handleSave}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                disabled={saving}
              >
                {saving ? 'Сохранение...' : '💾 Сохранить настройки'}
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default CompanySettingsPage;
