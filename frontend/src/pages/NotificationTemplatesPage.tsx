import React, { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import apiClient from '../api/client';

const NotificationTemplatesPage: React.FC = () => {
  const [templates, setTemplates] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState({ subject: '', body: '' });

  const loadTemplates = async () => {
    try {
      const res = await apiClient.get('/shifts/notification-templates');
      setTemplates(Array.isArray(res.data) ? res.data : []);
    } catch {} finally { setLoading(false); }
  };

  useEffect(() => { loadTemplates(); }, []);

  const initDefaults = async () => {
    try {
      const res = await apiClient.post('/shifts/notification-templates/init-defaults');
      alert(`✅ Создано ${res.data.created} шаблонов`);
      loadTemplates();
    } catch {}
  };

  const saveTemplate = async (id: number) => {
    try {
      await apiClient.put(`/shifts/notification-templates/${id}`, editForm);
      alert('✅ Шаблон обновлён');
      setEditingId(null);
      loadTemplates();
    } catch (err: any) { alert('Ошибка: ' + (err.response?.data?.detail || '')); }
  };

  const channelIcons: Record<string, string> = { max: '📨', email: '✉️', fcm: '🔔' };

  return (
    <Layout>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">📝 Шаблоны уведомлений</h1>
          <button onClick={initDefaults} className="px-3 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200">🔄 Создать стандартные</button>
        </div>

        {loading ? (
          <div className="flex justify-center py-12"><div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600"></div></div>
        ) : (
          <div className="space-y-3">
            {templates.map((t: any) => (
              <div key={t.id} className="bg-white rounded-xl shadow-sm border p-4">
                {editingId === t.id ? (
                  <div className="space-y-3">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-lg">{channelIcons[t.channel] || '📄'}</span>
                      <span className="font-mono text-sm text-gray-500">{t.code}/{t.channel}</span>
                    </div>
                    <label className="block"><span className="text-xs text-gray-500">Тема</span>
                      <input value={editForm.subject} onChange={e => setEditForm({...editForm, subject: e.target.value})} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" /></label>
                    <label className="block"><span className="text-xs text-gray-500">Текст</span>
                      <textarea value={editForm.body} onChange={e => setEditForm({...editForm, body: e.target.value})} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm font-mono" rows={3} /></label>
                    <div className="flex gap-2">
                      <button onClick={() => saveTemplate(t.id)} className="px-3 py-1.5 bg-green-600 text-white rounded text-sm">💾</button>
                      <button onClick={() => setEditingId(null)} className="px-3 py-1.5 text-gray-500 text-sm">✕</button>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-lg">{channelIcons[t.channel] || '📄'}</span>
                        <span className="font-mono text-sm font-bold text-gray-700">{t.code}</span>
                        <span className="px-1.5 py-0.5 bg-gray-100 rounded text-xs text-gray-500">{t.channel}</span>
                        {!t.is_active && <span className="px-1.5 py-0.5 bg-red-100 rounded text-xs text-red-600">inactive</span>}
                      </div>
                      <p className="text-sm text-gray-600 mt-1"><strong>{t.subject}</strong></p>
                      <p className="text-xs text-gray-400 mt-0.5 font-mono">{t.body.substring(0, 100)}{t.body.length > 100 ? '...' : ''}</p>
                    </div>
                    <button onClick={() => { setEditingId(t.id); setEditForm({ subject: t.subject || '', body: t.body }); }}
                      className="px-2 py-1 bg-indigo-100 text-indigo-700 rounded text-xs font-medium hover:bg-indigo-200">✏️</button>
                  </div>
                )}
              </div>
            ))}
            {templates.length === 0 && <p className="text-gray-400 text-center py-8">Нет шаблонов. Нажмите «Создать стандартные».</p>}
          </div>
        )}
      </div>
    </Layout>
  );
};

export default NotificationTemplatesPage;
