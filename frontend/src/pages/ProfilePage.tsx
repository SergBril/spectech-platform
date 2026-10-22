import React, { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import apiClient from '../api/client';

const ProfilePage: React.FC = () => {
  const [profile, setProfile] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [editMode, setEditMode] = useState(false);
  const [form, setForm] = useState({ full_name: '', phone: '' });
  const [bindLink, setBindLink] = useState('');
  const [roleHistory, setRoleHistory] = useState<any[]>([]);

  useEffect(() => {
    apiClient.get('/shifts/profile/me').then(res => {
      setProfile(res.data);
      setForm({ full_name: res.data.full_name || '', phone: res.data.phone || '' });
    }).catch(() => {}).finally(() => setLoading(false));

    // Load role history
    apiClient.get(`/shifts/audit-logs/role-history/${profile?.id || 0}`).then(res => {
      setRoleHistory(Array.isArray(res.data) ? res.data : []);
    }).catch(() => {});
  }, []);

  const saveProfile = async () => {
    try {
      await apiClient.put('/shifts/profile/me', form);
      alert('✅ Профиль обновлён');
      setEditMode(false);
      const res = await apiClient.get('/shifts/profile/me');
      setProfile(res.data);
    } catch (err: any) { alert('Ошибка: ' + (err.response?.data?.detail || '')); }
  };

  const getBindLink = async () => {
    try {
      const res = await apiClient.get('/shifts/max/bind-link');
      setBindLink(res.data.link);
    } catch {}
  };

  const unbindMax = async () => {
    if (!confirm('Отвязать MAX?')) return;
    try {
      await apiClient.post('/shifts/profile/unbind-max');
      alert('✅ MAX отвязан');
      const res = await apiClient.get('/shifts/profile/me');
      setProfile(res.data);
      setBindLink('');
    } catch {}
  };

  const testMax = async () => {
    try {
      const res = await apiClient.post('/shifts/max/test-webhook');
      alert('✅ ' + JSON.stringify(res.data.result));
    } catch (err: any) { alert('Ошибка: ' + (err.response?.data?.detail || '')); }
  };

  const roleLabels: Record<string, string> = { admin: '👑 Админ', dispatcher: '📋 Диспетчер', driver: '🚗 Водитель', accountant: '💰 Бухгалтер', viewer: '👁️ Наблюдатель' };

  if (loading) return <Layout><div className="flex justify-center py-12"><div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600"></div></div></Layout>;

  return (
    <Layout>
      <div className="p-6 max-w-2xl mx-auto space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">👤 Мой профиль</h1>

        {/* Profile Card */}
        <div className="bg-white rounded-xl shadow-sm border p-6 space-y-4">
          {editMode ? (
            <>
              <label className="block"><span className="text-xs text-gray-500">ФИО</span>
                <input value={form.full_name} onChange={e => setForm({...form, full_name: e.target.value})} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" /></label>
              <label className="block"><span className="text-xs text-gray-500">Телефон</span>
                <input value={form.phone} onChange={e => setForm({...form, phone: e.target.value})} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" /></label>
              <div className="flex gap-3">
                <button onClick={saveProfile} className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium">💾 Сохранить</button>
                <button onClick={() => setEditMode(false)} className="px-4 py-2 text-gray-600 text-sm">Отмена</button>
              </div>
            </>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div><span className="text-gray-500">Email:</span> <strong>{profile?.email}</strong></div>
                <div><span className="text-gray-500">ФИО:</span> <strong>{profile?.full_name || '—'}</strong></div>
                <div><span className="text-gray-500">Телефон:</span> <strong>{profile?.phone || '—'}</strong></div>
                <div><span className="text-gray-500">Роль:</span> <strong>{roleLabels[profile?.role] || profile?.role}</strong></div>
                <div><span className="text-gray-500">Статус:</span> <span className="px-2 py-0.5 bg-green-100 text-green-700 rounded text-xs">{profile?.status}</span></div>
                <div><span className="text-gray-500">Последний вход:</span> {profile?.last_login_at ? new Date(profile.last_login_at).toLocaleString('ru-RU') : '—'}</div>
              </div>
              <button onClick={() => setEditMode(true)} className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium">✏️ Редактировать</button>
            </>
          )}
        </div>

        {/* MAX Binding */}
        <div className="bg-white rounded-xl shadow-sm border p-6 space-y-4">
          <h2 className="text-lg font-bold flex items-center gap-2">📨 MAX Мессенджер</h2>
          {profile?.max_bound ? (
            <div className="space-y-3">
              <div className="flex items-center gap-2"><span className="px-2 py-1 bg-green-100 text-green-700 rounded text-xs font-medium">✅ Привязан</span>
                <span className="text-xs text-gray-400 font-mono">{profile.max_chat_id}</span></div>
              <div className="flex gap-3">
                <button onClick={testMax} className="px-3 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium">🧪 Тест</button>
                <button onClick={unbindMax} className="px-3 py-2 bg-red-100 text-red-700 rounded-lg text-sm font-medium">🔓 Отвязать</button>
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-sm text-gray-500">Привяжите MAX для получения уведомлений</p>
              {!bindLink ? (
                <button onClick={getBindLink} className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium">🔗 Получить ссылку</button>
              ) : (
                <div className="space-y-2">
                  <a href={bindLink} target="_blank" rel="noopener noreferrer" className="block px-4 py-3 bg-indigo-50 border border-indigo-200 rounded-lg text-sm text-indigo-700 font-medium hover:bg-indigo-100 break-all">
                    {bindLink}
                  </a>
                  <p className="text-xs text-gray-400">Нажмите ссылку → откроется MAX → нажмите «Начать» в боте</p>
                </div>
              )}
            </div>
          )}
        </div>
        {/* Role History */}
        {roleHistory.length > 0 && (
          <div className="bg-white rounded-xl shadow-sm border p-6 space-y-3">
            <h2 className="text-lg font-bold">📋 История изменений роли</h2>
            <div className="space-y-2">
              {roleHistory.map((h: any) => (
                <div key={h.id} className="flex items-center justify-between text-sm py-2 border-b last:border-0">
                  <span className="text-gray-600">{h.details || h.action}</span>
                  <span className="text-xs text-gray-400 whitespace-nowrap">{h.created_at ? new Date(h.created_at).toLocaleString('ru-RU') : ''}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default ProfilePage;
