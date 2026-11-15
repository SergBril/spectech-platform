import React, { useCallback, useEffect, useState } from 'react';
import Layout from '../components/Layout';
import apiClient from '../api/client';

interface EdoForm {
  operator: string;
  diadoc_box_id: string;
  diadoc_use_sandbox: boolean;
  sbis_client_id: string;
  auto_send_on_sign: boolean;
  default_format: string;
}

interface SecretState {
  set: boolean;
  mask: string;
}

const errorDetail = (err: unknown, fallback: string): string => {
  const e = err as { response?: { data?: { detail?: unknown } }; message?: unknown };
  if (typeof e?.response?.data?.detail === 'string') return e.response.data.detail;
  if (typeof e?.message === 'string') return e.message;
  return fallback;
};

const EdoSettingsPage: React.FC = () => {
  const [form, setForm] = useState<EdoForm>({
    operator: 'diadoc',
    diadoc_box_id: '',
    diadoc_use_sandbox: true,
    sbis_client_id: '',
    auto_send_on_sign: false,
    default_format: 'upd_5_03',
  });
  const [secrets, setSecrets] = useState<{ diadoc: SecretState; sbis: SecretState }>({
    diadoc: { set: false, mask: '' },
    sbis: { set: false, mask: '' },
  });
  const [newDiadocKey, setNewDiadocKey] = useState('');
  const [newSbisToken, setNewSbisToken] = useState('');
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [savedOk, setSavedOk] = useState(false);
  const [busySecret, setBusySecret] = useState<'diadoc_api_key' | 'sbis_token' | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError('');
    try {
      const res = await apiClient.get('/edo-settings');
      const d = res.data;
      setForm({
        operator: d.operator ?? 'diadoc',
        diadoc_box_id: d.diadoc_box_id ?? '',
        diadoc_use_sandbox: d.diadoc_use_sandbox ?? true,
        sbis_client_id: d.sbis_client_id ?? '',
        auto_send_on_sign: d.auto_send_on_sign ?? false,
        default_format: d.default_format ?? 'upd_5_03',
      });
      setSecrets({
        diadoc: { set: Boolean(d.diadoc_api_key_set), mask: d.diadoc_api_key ?? '' },
        sbis: { set: Boolean(d.sbis_token_set), mask: d.sbis_token ?? '' },
      });
      setNewDiadocKey('');
      setNewSbisToken('');
    } catch (err) {
      setLoadError(errorDetail(err, 'Не удалось загрузить настройки ЭДО'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const save = async () => {
    setSaving(true);
    setSaveError('');
    setSavedOk(false);
    const payload: Record<string, string | boolean> = {
      operator: form.operator,
      diadoc_box_id: form.diadoc_box_id,
      diadoc_use_sandbox: form.diadoc_use_sandbox,
      sbis_client_id: form.sbis_client_id,
      auto_send_on_sign: form.auto_send_on_sign,
      default_format: form.default_format,
    };
    // Секрет включается в payload только если введено новое значение:
    // отсутствие поля = не менять, маска не отправляется никогда.
    if (newDiadocKey.trim() !== '') payload.diadoc_api_key = newDiadocKey.trim();
    if (newSbisToken.trim() !== '') payload.sbis_token = newSbisToken.trim();
    try {
      await apiClient.put('/edo-settings', payload);
      setSavedOk(true);
      await load();
    } catch (err) {
      setSaveError(errorDetail(err, 'Не удалось сохранить настройки'));
    } finally {
      setSaving(false);
    }
  };

  const deleteSecret = async (field: 'diadoc_api_key' | 'sbis_token') => {
    setBusySecret(field);
    setSaveError('');
    setSavedOk(false);
    try {
      // Пустая строка — явное удаление секрета на backend.
      await apiClient.put('/edo-settings', { [field]: '' });
      await load();
    } catch (err) {
      setSaveError(errorDetail(err, 'Не удалось удалить секрет'));
    } finally {
      setBusySecret(null);
    }
  };

  const operators = [
    { value: 'diadoc', label: '🟢 Диадок (Контур)', desc: 'Самый популярный оператор ЭДО в РФ' },
    { value: 'sbis', label: '🔵 СБИС (Тензор)', desc: 'Второй по популярности оператор' },
    { value: 'kaluga', label: '🟡 Калуга Астрал', desc: 'Оператор для госучреждений' },
    { value: 'none', label: '⚪ Не выбран', desc: 'Только генерация XML без отправки' },
  ];

  if (loading) {
    return (
      <Layout>
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600"></div>
        </div>
      </Layout>
    );
  }

  if (loadError) {
    return (
      <Layout>
        <div className="p-6 max-w-2xl mx-auto">
          <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 space-y-2">
            <p className="font-semibold">❌ {loadError}</p>
            <p className="text-xs">
              Настройки не загружены. Сохранение заблокировано, чтобы не перезаписать
              реальные значения дефолтами.
            </p>
            <button
              onClick={load}
              className="px-3 py-1.5 bg-red-600 text-white rounded-lg text-xs font-medium hover:bg-red-700 transition"
            >
              Повторить загрузку
            </button>
          </div>
        </div>
      </Layout>
    );
  }

  const secretBadge = (secret: SecretState, label: string) =>
    secret.set ? (
      <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-green-50 border border-green-200 text-xs text-green-700">
        🔑 {label} задан ({secret.mask})
      </span>
    ) : (
      <span className="inline-flex items-center px-2 py-1 rounded-full bg-gray-50 border border-gray-200 text-xs text-gray-500">
        {label} не задан
      </span>
    );

  return (
    <Layout>
      <div className="p-6 max-w-2xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">📡 Настройки ЭДО</h1>
          <button
            onClick={save}
            disabled={saving || busySecret !== null}
            className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50 transition"
          >
            {saving ? '⏳ Сохранение...' : '💾 Сохранить'}
          </button>
        </div>

        {savedOk && (
          <div role="status" className="rounded-xl border border-green-200 bg-green-50 p-3 text-sm text-green-700">
            ✅ Настройки ЭДО сохранены
          </div>
        )}
        {saveError && (
          <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            ❌ {saveError}
          </div>
        )}

        {/* Operator Selection */}
        <div className="bg-white rounded-xl shadow-sm border p-5 space-y-3">
          <h2 className="font-bold text-gray-800">Оператор ЭДО</h2>
          <div className="grid grid-cols-1 gap-2">
            {operators.map(op => (
              <label
                key={op.value}
                className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${form.operator === op.value ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:bg-gray-50'}`}
              >
                <input
                  type="radio"
                  name="operator"
                  value={op.value}
                  checked={form.operator === op.value}
                  onChange={e => setForm(prev => ({ ...prev, operator: e.target.value }))}
                  className="mt-1"
                />
                <div>
                  <span className="font-medium text-sm">{op.label}</span>
                  <p className="text-xs text-gray-500">{op.desc}</p>
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* Diadoc Settings */}
        {form.operator === 'diadoc' && (
          <div className="bg-white rounded-xl shadow-sm border p-5 space-y-3">
            <h2 className="font-bold text-gray-800">🟢 Настройки Диадок</h2>

            <div>
              <div className="flex items-center gap-2 flex-wrap">
                {secretBadge(secrets.diadoc, 'Ключ')}
                {secrets.diadoc.set && (
                  <button
                    onClick={() => deleteSecret('diadoc_api_key')}
                    disabled={busySecret !== null || saving}
                    className="text-xs text-red-600 hover:text-red-800 underline disabled:opacity-50"
                  >
                    {busySecret === 'diadoc_api_key' ? '⏳ Удаление...' : 'Удалить ключ'}
                  </button>
                )}
              </div>
              <label htmlFor="diadoc-new-key" className="block mt-2">
                <span className="text-xs text-gray-500">Новый ключ</span>
                <input
                  id="diadoc-new-key"
                  type="password"
                  value={newDiadocKey}
                  onChange={e => setNewDiadocKey(e.target.value)}
                  autoComplete="new-password"
                  className="w-full mt-1 px-3 py-2 border rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Оставьте пустым, чтобы не менять"
                />
              </label>
            </div>

            <label htmlFor="diadoc-box-id" className="block">
              <span className="text-xs text-gray-500">Box ID</span>
              <input
                id="diadoc-box-id"
                value={form.diadoc_box_id}
                onChange={e => setForm(prev => ({ ...prev, diadoc_box_id: e.target.value }))}
                className="w-full mt-1 px-3 py-2 border rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Идентификатор ящика организации"
              />
            </label>

            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={form.diadoc_use_sandbox}
                onChange={e => setForm(prev => ({ ...prev, diadoc_use_sandbox: e.target.checked }))}
              />
              <span className="text-sm text-gray-700">Использовать песочницу (тестовый режим)</span>
            </label>

            {!form.diadoc_use_sandbox && (
              <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700">
                ⚠️ Песочница выключена: отправки идут в <strong>БОЕВОЙ Диадок</strong>{' '}
                (diadoc-api.kontur.ru) и создают <strong>настоящие документы</strong> у контрагентов.
                Включите песочницу для тестовых отправок.
              </div>
            )}
          </div>
        )}

        {/* SBIS Settings */}
        {form.operator === 'sbis' && (
          <div className="bg-white rounded-xl shadow-sm border p-5 space-y-3">
            <h2 className="font-bold text-gray-800">🔵 Настройки СБИС</h2>

            <div>
              <div className="flex items-center gap-2 flex-wrap">
                {secretBadge(secrets.sbis, 'Токен')}
                {secrets.sbis.set && (
                  <button
                    onClick={() => deleteSecret('sbis_token')}
                    disabled={busySecret !== null || saving}
                    className="text-xs text-red-600 hover:text-red-800 underline disabled:opacity-50"
                  >
                    {busySecret === 'sbis_token' ? '⏳ Удаление...' : 'Удалить токен'}
                  </button>
                )}
              </div>
              <label htmlFor="sbis-new-token" className="block mt-2">
                <span className="text-xs text-gray-500">Новый токен</span>
                <input
                  id="sbis-new-token"
                  type="password"
                  value={newSbisToken}
                  onChange={e => setNewSbisToken(e.target.value)}
                  autoComplete="new-password"
                  className="w-full mt-1 px-3 py-2 border rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Оставьте пустым, чтобы не менять"
                />
              </label>
            </div>

            <label htmlFor="sbis-client-id" className="block">
              <span className="text-xs text-gray-500">Client ID</span>
              <input
                id="sbis-client-id"
                value={form.sbis_client_id}
                onChange={e => setForm(prev => ({ ...prev, sbis_client_id: e.target.value }))}
                className="w-full mt-1 px-3 py-2 border rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Идентификатор клиента"
              />
            </label>
          </div>
        )}

        {/* General Settings */}
        <div className="bg-white rounded-xl shadow-sm border p-5 space-y-3">
          <h2 className="font-bold text-gray-800">⚙️ Общие настройки</h2>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={form.auto_send_on_sign}
              onChange={e => setForm(prev => ({ ...prev, auto_send_on_sign: e.target.checked }))}
            />
            <span className="text-sm text-gray-700">Автоматически отправлять в ЭДО при подписании акта</span>
          </label>
          <label htmlFor="edo-default-format" className="block">
            <span className="text-xs text-gray-500">Формат документа</span>
            <select
              id="edo-default-format"
              value={form.default_format}
              onChange={e => setForm(prev => ({ ...prev, default_format: e.target.value }))}
              className="w-full mt-1 px-3 py-2 border rounded-lg text-sm"
            >
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
