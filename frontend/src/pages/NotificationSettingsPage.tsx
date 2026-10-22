import React, { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import apiClient from '../api/client';

const NotificationSettingsPage: React.FC = () => {
  const [settings, setSettings] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    apiClient.get('/shifts/profile/notification-settings')
      .then(res => setSettings(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const toggle = (key: string) => setSettings(prev => ({ ...prev, [key]: !prev[key] }));

  const save = async () => {
    setSaving(true);
    try {
      await apiClient.put('/shifts/profile/notification-settings', settings);
      alert('✅ Настройки сохранены');
    } catch {} finally { setSaving(false); }
  };

  const groups = [
    { title: '🔑 Смена роли', keys: [['notify_role_change_max', 'MAX'], ['notify_role_change_email', 'Email']] },
    { title: '💸 Просроченные акты', keys: [['notify_overdue_max', 'MAX'], ['notify_overdue_email', 'Email']] },
    { title: '✅ Подписание акта', keys: [['notify_act_signed_max', 'MAX'], ['notify_act_signed_email', 'Email']] },
  ];

  if (loading) return <Layout><div className="flex justify-center py-12"><div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600"></div></div></Layout>;

  return (
    <Layout>
      <div className="p-6 max-w-xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">🔔 Настройки уведомлений</h1>
          <button onClick={save} disabled={saving} className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium disabled:opacity-50">
            {saving ? '⏳...' : '💾 Сохранить'}
          </button>
        </div>

        {groups.map(g => (
          <div key={g.title} className="bg-white rounded-xl shadow-sm border p-5 space-y-3">
            <h2 className="font-bold text-gray-800">{g.title}</h2>
            {g.keys.map(([key, label]) => (
              <label key={key} className="flex items-center justify-between cursor-pointer">
                <span className="text-sm text-gray-700">{label}</span>
                <div className={`w-11 h-6 rounded-full transition-colors relative ${settings[key] ? 'bg-green-500' : 'bg-gray-300'}`}
                  onClick={() => toggle(key)}>
                  <div className={`w-5 h-5 bg-white rounded-full absolute top-0.5 transition-transform ${settings[key] ? 'left-[22px]' : 'left-0.5'}`} />
                </div>
              </label>
            ))}
          </div>
        ))}
      </div>
    </Layout>
  );
};

export default NotificationSettingsPage;
