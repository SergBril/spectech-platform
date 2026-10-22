import React, { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import apiClient from '../api/client';

const EdoSettingsPage: React.FC = () => {
  const [settings, setSettings] = useState({
    operator: 'diadoc',
    diadoc_api_key: '',
    diadoc_box_id: '',
    diadoc_use_sandbox: true,
    sbis_token: '',
    sbis_client_id: '',
    auto_send_on_sign: false,
    default_format: 'upd_5_03',
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    apiClient.get('/companies/edo-settings')
      .then(res => setSettings(prev => ({ ...prev, ...res.data })))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      await apiClient.put('/companies/edo-settings', settings);
      alert('✅ Настройки ЭДО сохранены');
    } catch (err: any) { alert('Ошибка: ' + (err.response?.data?.detail || '')); }
    finally { setSaving(false); }
  };

  const operators = [
    { value: 'diadoc', label: '🟢 Диадок (Контур)', desc: 'Самый популярный оператор ЭДО в РФ' },
    { value: 'sbis', label: '🔵 СБИС (Тензор)', desc: 'Второй по популярности оператор' },
    { value: 'kaluga', label: '🟡 Калуга Астрал', desc: 'Оператор для госучреждений' },
    { value: 'none', label: '⚪ Не выбран', desc: 'Только генерация XML без отправки' },
  ];

  if (loading) return <Layout><div className="flex justify-center py-12"><div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600"></div></div></Layout>;

  return (
    <Layout>
      <div className="p-6 max-w-2xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">📡 Настройки ЭДО</h1>
          <button onClick={save} disabled={saving} className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium disabled:opacity-50">
            {saving ? '⏳...' : '💾 Сохранить'}
          </button>
        </div>

        {/* Operator Selection */}
        <div className="bg-white rounded-xl shadow-sm border p-5 space-y-3">
          <h2 className="font-bold text-gray-800">Оператор ЭДО</h2>
          <div className="grid grid-cols-1 gap-2">
            {operators.map(op => (
              <label key={op.value} className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${settings.operator === op.value ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:bg-gray-50'}`}>
                <input type="radio" name="operator" value={op.value} checked={settings.operator === op.value}
                  onChange={e => setSettings(prev => ({ ...prev, operator: e.target.value }))} className="mt-1" />
                <div>
                  <span className="font-medium text-sm">{op.label}</span>
                  <p className="text-xs text-gray-500">{op.desc}</p>
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* Diadoc Settings */}
        {settings.operator === 'diadoc' && (
          <div className="bg-white rounded-xl shadow-sm border p-5 space-y-3">
            <h2 className="font-bold text-gray-800">🟢 Настройки Диадок</h2>
            <label className="block"><span className="text-xs text-gray-500">API Key</span>
              <input type="password" value={settings.diadoc_api_key} onChange={e => setSettings({...settings, diadoc_api_key: e.target.value})}
                className="w-full mt-1 px-3 py-2 border rounded-lg text-sm font-mono" placeholder="Получите в личном кабинете Диадок" /></label>
            <label className="block"><span className="text-xs text-gray-500">Box ID</span>
              <input value={settings.diadoc_box_id} onChange={e => setSettings({...settings, diadoc_box_id: e.target.value})}
                className="w-full mt-1 px-3 py-2 border rounded-lg text-sm font-mono" placeholder="Идентификатор ящика организации" /></label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={settings.diadoc_use_sandbox} onChange={e => setSettings({...settings, diadoc_use_sandbox: e.target.checked})} />
              <span className="text-sm text-gray-700">Использовать песочницу (тестовый режим)</span>
            </label>
          </div>
        )}

        {/* SBIS Settings */}
        {settings.operator === 'sbis' && (
          <div className="bg-white rounded-xl shadow-sm border p-5 space-y-3">
            <h2 className="font-bold text-gray-800">🔵 Настройки СБИС</h2>
            <label className="block"><span className="text-xs text-gray-500">Token</span>
              <input type="password" value={settings.sbis_token} onChange={e => setSettings({...settings, sbis_token: e.target.value})}
                className="w-full mt-1 px-3 py-2 border rounded-lg text-sm font-mono" placeholder="Токен доступа СБИС" /></label>
            <label className="block"><span className="text-xs text-gray-500">Client ID</span>
              <input value={settings.sbis_client_id} onChange={e => setSettings({...settings, sbis_client_id: e.target.value})}
                className="w-full mt-1 px-3 py-2 border rounded-lg text-sm font-mono" placeholder="Идентификатор клиента" /></label>
          </div>
        )}

        {/* General Settings */}
        <div className="bg-white rounded-xl shadow-sm border p-5 space-y-3">
          <h2 className="font-bold text-gray-800">⚙️ Общие настройки</h2>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={settings.auto_send_on_sign} onChange={e => setSettings({...settings, auto_send_on_sign: e.target.checked})} />
            <span className="text-sm text-gray-700">Автоматически отправлять в ЭДО при подписании акта</span>
          </label>
          <label className="block"><span className="text-xs text-gray-500">Формат документа</span>
            <select value={settings.default_format} onChange={e => setSettings({...settings, default_format: e.target.value})}
              className="w-full mt-1 px-3 py-2 border rounded-lg text-sm">
              <option value="upd_5_03">УПД формат 5.03 (ФНС, с 01.01.2026)</option>
              <option value="upd_5_02">УПД формат 5.02 (устаревший)</option>
            </select>
          </label>
        </div>

        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 text-sm text-yellow-800">
          <strong>ℹ️ Примечание:</strong> Для работы с ЭДО необходима квалифицированная электронная подпись (КЭП). 
          XML генерируется по формату ФНС 5.03 (приказ ЕД-7-26/970@ в ред. ЕД-7-26/1032@).
          Подписание осуществляется через сервис подписи платформы или внешний криптопровайдер.
        </div>
      </div>
    </Layout>
  );
};

export default EdoSettingsPage;
