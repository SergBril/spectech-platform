import React, { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import apiClient from '../api/client';

const ChecklistConfigsPage: React.FC = () => {
  const [configs, setConfigs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: '', vehicle_category_id: '', items: [{ key: '', label: '', required: true }] });

  const loadConfigs = async () => {
    try {
      const res = await apiClient.get('/shifts/checklist-configs');
      setConfigs(Array.isArray(res.data) ? res.data : []);
    } catch {} finally { setLoading(false); }
  };

  useEffect(() => { loadConfigs(); }, []);

  const addItem = () => setForm({ ...form, items: [...form.items, { key: '', label: '', required: true }] });
  const removeItem = (i: number) => setForm({ ...form, items: form.items.filter((_, idx) => idx !== i) });
  const updateItem = (i: number, field: string, value: any) => {
    const updated = [...form.items];
    updated[i] = { ...updated[i], [field]: value };
    setForm({ ...form, items: updated });
  };

  const saveConfig = async () => {
    if (!form.name || form.items.some(it => !it.key || !it.label)) {
      alert('Заполните название и все пункты чеклиста'); return;
    }
    try {
      await apiClient.post('/shifts/checklist-configs', {
        name: form.name,
        vehicle_category_id: form.vehicle_category_id ? Number(form.vehicle_category_id) : null,
        items: form.items,
      });
      setShowForm(false);
      setForm({ name: '', vehicle_category_id: '', items: [{ key: '', label: '', required: true }] });
      loadConfigs();
    } catch (err: any) { alert('Ошибка: ' + (err.response?.data?.detail || '')); }
  };

  const deleteConfig = async (id: number) => {
    if (!confirm('Удалить конфигурацию чеклиста?')) return;
    try { await apiClient.delete(`/shifts/checklist-configs/${id}`); loadConfigs(); }
    catch (err: any) { alert('Ошибка: ' + (err.response?.data?.detail || '')); }
  };

  return (
    <Layout>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">⚙️ Чеклисты по типам техники</h1>
          <button onClick={() => setShowForm(!showForm)}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 text-sm font-medium">
            {showForm ? '✕ Отмена' : '➕ Новый чеклист'}
          </button>
        </div>

        {/* Create Form */}
        {showForm && (
          <div className="bg-white rounded-xl shadow-sm border p-5 space-y-4">
            <h2 className="text-sm font-semibold text-gray-500 uppercase">Новая конфигурация</h2>
            <div className="grid grid-cols-2 gap-3">
              <label className="block"><span className="text-xs text-gray-500">Название</span>
                <input value={form.name} onChange={e => setForm({...form, name: e.target.value})}
                  className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" placeholder="Например: Крановая установка" /></label>
              <label className="block"><span className="text-xs text-gray-500">Категория техники (ID, пусто = общий)</span>
                <input type="number" value={form.vehicle_category_id} onChange={e => setForm({...form, vehicle_category_id: e.target.value})}
                  className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" placeholder="Оставьте пустым для общего" /></label>
            </div>
            <div>
              <div className="flex justify-between items-center mb-2">
                <span className="text-xs font-semibold text-gray-500 uppercase">Пункты чеклиста</span>
                <button onClick={addItem} className="text-xs text-indigo-600 hover:text-indigo-800 font-medium">+ Пункт</button>
              </div>
              <div className="space-y-2">
                {form.items.map((item, i) => (
                  <div key={i} className="flex gap-2 items-center">
                    <input placeholder="Ключ (eng)" value={item.key} onChange={e => updateItem(i, 'key', e.target.value)}
                      className="w-28 px-2 py-1.5 border rounded text-xs" />
                    <input placeholder="Название пункта" value={item.label} onChange={e => updateItem(i, 'label', e.target.value)}
                      className="flex-1 px-2 py-1.5 border rounded text-xs" />
                    <label className="flex items-center gap-1 text-xs whitespace-nowrap">
                      <input type="checkbox" checked={item.required} onChange={e => updateItem(i, 'required', e.target.checked)} /> Обяз.
                    </label>
                    <button onClick={() => removeItem(i)} className="text-red-400 hover:text-red-600 text-sm">✕</button>
                  </div>
                ))}
              </div>
            </div>
            <button onClick={saveConfig}
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 text-sm font-medium">
              💾 Сохранить конфигурацию
            </button>
          </div>
        )}

        {/* Configs List */}
        {loading ? <div className="animate-pulse h-20 bg-gray-100 rounded-xl"></div> : (
          <div className="space-y-3">
            {configs.length === 0 ? (
              <p className="text-gray-400 text-center py-8">Нет конфигураций. Создайте первую.</p>
            ) : configs.map((c: any) => (
              <div key={c.id} className="bg-white rounded-xl shadow-sm border p-4">
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <h3 className="font-bold text-gray-900">{c.name}</h3>
                    <p className="text-xs text-gray-500">
                      {c.vehicle_category_id ? `Категория #${c.vehicle_category_id}` : '📋 Общий (все категории)'} • {c.items.length} пунктов
                    </p>
                  </div>
                  <button onClick={() => deleteConfig(c.id)} className="text-red-500 hover:text-red-700 text-sm">🗑️</button>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {c.items.map((it: any, i: number) => (
                    <span key={i} className={`px-2 py-0.5 rounded text-xs ${it.required ? 'bg-red-50 text-red-700 border border-red-200' : 'bg-gray-50 text-gray-600 border border-gray-200'}`}>
                      {it.label}{it.required && ' *'}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Layout>
  );
};

export default ChecklistConfigsPage;
