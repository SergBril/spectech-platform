import React, { useEffect, useState } from 'react';
import { showToast } from '../utils/toast';
import { mapApi, GpsProviderOption } from '../api/map';
import apiClient from '../api/client';

interface GpsProviderConfig {
  api_key?: string;
  api_url?: string;
  unit_id?: string;
  device_id?: string;
  login?: string;
  password?: string;
}

interface Props {
  value: { provider: string; config: GpsProviderConfig } | null;
  onChange: (value: { provider: string; config: GpsProviderConfig } | null) => void;
}

const PROVIDER_FIELDS: Record<string, { key: keyof GpsProviderConfig; label: string; type?: string; placeholder?: string }[]> = {
  wialon: [
    { key: 'login', label: 'Логин', placeholder: 'user@example.com' },
    { key: 'password', label: 'Пароль', type: 'password', placeholder: '••••••••' },
    { key: 'unit_id', label: 'Unit ID', placeholder: 'ID объекта в Wialon' },
    { key: 'api_url', label: 'API URL (опционально)', placeholder: 'https://hst-api.wialon.com/wialon/ajax.html' },
  ],
  gdemoi: [
    { key: 'api_key', label: 'API Key', placeholder: 'Ключ API ГдеМои' },
    { key: 'device_id', label: 'Device ID', placeholder: 'ID устройства' },
    { key: 'api_url', label: 'API URL (опционально)', placeholder: 'https://api.gdemoi.ru' },
  ],
  gps_trace: [
    { key: 'api_key', label: 'API Key', placeholder: 'X-API-Key' },
    { key: 'unit_id', label: 'Unit ID', placeholder: 'ID юнита' },
    { key: 'api_url', label: 'API URL (опционально)', placeholder: 'https://api.gps-trace.com' },
  ],
  mapix: [
    { key: 'api_key', label: 'API Key', placeholder: 'Bearer token Mapix' },
    { key: 'device_id', label: 'Device ID', placeholder: 'ID устройства' },
    { key: 'api_url', label: 'API URL (опционально)', placeholder: 'https://api.mapix.su' },
  ],
  manual: [],
};

export const GpsProviderSelector: React.FC<Props> = ({ value, onChange }) => {
  const [providers, setProviders] = useState<GpsProviderOption[]>([]);
  const [selectedProvider, setSelectedProvider] = useState(value?.provider || '');
  const [config, setConfig] = useState<GpsProviderConfig>(value?.config || {});
  const [testing, setTesting] = useState(false);
  const [showRequestForm, setShowRequestForm] = useState(false);
  const [requestName, setRequestName] = useState('');
  const [requestUrl, setRequestUrl] = useState('');
  const [requestComment, setRequestComment] = useState('');
  const [sendingRequest, setSendingRequest] = useState(false);

  useEffect(() => {
    mapApi.getGpsProviders().then((data) => setProviders(data.providers)).catch(() => {});
  }, []);

  useEffect(() => {
    if (value) {
      setSelectedProvider(value.provider);
      setConfig(value.config || {});
    }
  }, [value]);

  const handleProviderChange = (provider: string) => {
    setSelectedProvider(provider);
    setConfig({});
    setShowRequestForm(false);
    if (!provider) {
      onChange(null);
    } else {
      onChange({ provider, config: {} });
    }
  };

  const handleConfigChange = (key: keyof GpsProviderConfig, val: string) => {
    const newConfig = { ...config, [key]: val };
    setConfig(newConfig);
    onChange({ provider: selectedProvider, config: newConfig });
  };

  const handleTest = async () => {
    if (!selectedProvider) return;
    try {
      setTesting(true);
      const result = await mapApi.testGpsProvider(selectedProvider, config);
      if (result.success) {
        showToast.success(`✅ Соединение с ${selectedProvider} установлено`);
      } else {
        showToast.error(`❌ Ошибка: ${result.error || 'Не удалось подключиться'}`);
      }
    } catch (err: any) {
      showToast.error('Ошибка проверки: ' + (err?.response?.data?.detail || err.message));
    } finally {
      setTesting(false);
    }
  };

  const handleSendRequest = async () => {
    if (!requestName.trim()) {
      showToast.error('Укажите название провайдера');
      return;
    }
    try {
      setSendingRequest(true);
      await apiClient.post('/map/providers/request', {
        provider_name: requestName.trim(),
        provider_url: requestUrl.trim() || undefined,
        comment: requestComment.trim() || undefined,
      });
      showToast.success('✅ Заявка отправлена! Мы добавим провайдера в ближайшее время.');
      setShowRequestForm(false);
      setRequestName('');
      setRequestUrl('');
      setRequestComment('');
    } catch (err: any) {
      showToast.error('Ошибка: ' + (err?.response?.data?.detail || err.message));
    } finally {
      setSendingRequest(false);
    }
  };

  const fields = PROVIDER_FIELDS[selectedProvider] || [];

  return (
    <div className="space-y-3">
      <label className="block text-sm font-medium text-gray-700">📡 GPS-провайдер</label>
      <select
        value={selectedProvider}
        onChange={(e) => handleProviderChange(e.target.value)}
        className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
      >
        <option value="">— Не выбрано —</option>
        {providers.map((p) => (
          <option key={p.value} value={p.value}>{p.label}</option>
        ))}
        <option value="__request__">➕ Запросить нового провайдера...</option>
      </select>

      {/* Форма запроса нового провайдера */}
      {showRequestForm && (
        <div className="bg-amber-50 rounded-lg p-4 space-y-3 border border-amber-200">
          <div className="text-sm font-medium text-amber-900">📨 Запрос на добавление GPS-провайдера</div>
          <div>
            <label className="block text-xs font-medium text-amber-800 mb-0.5">Название провайдера *</label>
            <input
              type="text"
              value={requestName}
              onChange={(e) => setRequestName(e.target.value)}
              placeholder="Например: Navixy, Teltonika, StarLine"
              className="w-full border border-amber-300 rounded px-2 py-1.5 text-sm focus:ring-1 focus:ring-amber-500 outline-none bg-white"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-amber-800 mb-0.5">Сайт / API URL</label>
            <input
              type="text"
              value={requestUrl}
              onChange={(e) => setRequestUrl(e.target.value)}
              placeholder="https://..."
              className="w-full border border-amber-300 rounded px-2 py-1.5 text-sm focus:ring-1 focus:ring-amber-500 outline-none bg-white"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-amber-800 mb-0.5">Комментарий</label>
            <textarea
              value={requestComment}
              onChange={(e) => setRequestComment(e.target.value)}
              placeholder="Дополнительная информация..."
              rows={2}
              className="w-full border border-amber-300 rounded px-2 py-1.5 text-sm focus:ring-1 focus:ring-amber-500 outline-none bg-white resize-none"
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleSendRequest}
              disabled={sendingRequest}
              className="bg-amber-600 text-white px-3 py-1.5 rounded text-xs font-medium hover:bg-amber-700 disabled:opacity-50 transition-colors"
            >
              {sendingRequest ? '⏳ Отправка...' : '📨 Отправить заявку'}
            </button>
            <button
              onClick={() => { setShowRequestForm(false); setSelectedProvider(''); }}
              className="bg-white text-gray-600 px-3 py-1.5 rounded text-xs font-medium hover:bg-gray-100 border border-gray-300 transition-colors"
            >
              Отмена
            </button>
          </div>
        </div>
      )}

      {/* Конфигурация выбранного провайдера */}
      {selectedProvider && selectedProvider !== '__request__' && fields.length > 0 && (
        <div className="bg-gray-50 rounded-lg p-3 space-y-2 border border-gray-200">
          {fields.map((field) => (
            <div key={field.key}>
              <label className="block text-xs font-medium text-gray-600 mb-0.5">{field.label}</label>
              <input
                type={field.type || 'text'}
                value={config[field.key] || ''}
                onChange={(e) => handleConfigChange(field.key, e.target.value)}
                placeholder={field.placeholder}
                className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm focus:ring-1 focus:ring-blue-500 outline-none"
              />
            </div>
          ))}
          <button
            onClick={handleTest}
            disabled={testing}
            className="mt-2 bg-indigo-600 text-white px-3 py-1.5 rounded text-xs font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {testing ? '⏳ Проверка...' : '🔌 Проверить соединение'}
          </button>
        </div>
      )}

      {selectedProvider === 'manual' && (
        <div className="bg-blue-50 rounded-lg p-3 text-xs text-blue-700 border border-blue-200">
          📌 Данные будут приниматься напрямую через API / MQTT без стороннего провайдера.
        </div>
      )}
    </div>
  );
};

export default GpsProviderSelector;