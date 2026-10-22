import React, { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import apiClient from '../api/client';

const AutoAssignRulesPage: React.FC = () => {
  const [rules, setRules] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ name: '', rule_type: 'priority_driver', priority: 0, config: '{}' });

  const loadRules = async () => {
    try {
      const res = await apiClient.get('/shifts/auto-assign/rules');
      setRules(Array.isArray(res.data) ? res.data : []);
    } catch {} finally { setLoading(false); }
  };

  useEffect(() => { loadRules(); }, []);

  const createRule = async () => {
    try {
      let configObj = {};
      try { configObj = JSON.parse(form.config); } catch { alert('Некорректный JSON в конфигурации'); return; }
      await apiClient.post('/shifts/auto-assign/rules', { ...form, config: configObj });
      setForm({ name: '', rule_type: 'priority_driver', priority: 0, config: '{}' });
      loadRules();
    } catch (err: any) { alert('Ошибка: ' + (err.response?.data?.detail || '')); }
  };

  const deleteRule = async (id: number) => {
    if (!confirm('Удалить правило?')) return;
    try { await apiClient.delete(`/shifts/auto-assign/rules/${id}`); loadRules(); }
    catch (err: any) { alert('Ошибка: ' + (err.response?.data?.detail || '')); }
  };

  const typeLabels: Record<string, string> = {
    priority_driver: 'Приоритетный водитель', blacklist: 'Чёрный список', category_match: 'Совпадение категории',
  };

  return (
    <Layout>
      <div className="p-6 space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">⚙️ Правила авто-назначения водителей</h1>

        {/* Create form */}
        <div className="bg-white rounded-xl shadow-sm border p-5 space-y-3">
          <h2 className="text-sm font-semibold text-gray-500 uppercase">Новое правило</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <input placeholder="Название" value={form.name} onChange={e => setForm({...form, name: e.target.value})}
              className="px-3 py-2 border rounded-lg text-sm" />
            <select value={form.rule_type} onChange={e => setForm({...form, rule_type: e.target.value})}
              className="px-3 py-2 border rounded-lg text-sm">
              <option value="priority_driver">Приоритетный водитель</option>
              <option value="blacklist">Чёрный список</option>
              <option value="category_match">Совпадение категории</option>
            </select>
            <input type="number" placeholder="Приоритет" value={form.priority} onChange={e => setForm({...form, priority: Number(e.target.value)})}
              className="px-3 py-2 border rounded-lg text-sm" />
            <input placeholder='JSON конфиг {"driver_ids":[1,2]}' value={form.config} onChange={e => setForm({...form, config: e.target.value})}
              className="px-3 py-2 border rounded-lg text-sm col-span-2 md:col-span-1" />
          </div>
          <button onClick={createRule} disabled={!form.name}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 text-sm font-medium disabled:opacity-50">
            ➕ Добавить правило
          </button>
        </div>

        {/* Rules list */}
        {loading ? <div className="animate-pulse h-20 bg-gray-100 rounded-xl"></div> : (
          <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Название</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Тип</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Приоритет</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Конфиг</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Действия</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {rules.length === 0 ? (
                  <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400 text-sm">Нет правил. Создайте первое.</td></tr>
                ) : rules.map((r: any) => (
                  <tr key={r.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">{r.name}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">{typeLabels[r.rule_type] || r.rule_type}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">{r.priority}</td>
                    <td className="px-4 py-3 text-xs text-gray-500 font-mono max-w-[200px] truncate">{JSON.stringify(r.config)}</td>
                    <td className="px-4 py-3 text-right">
                      <button onClick={() => deleteRule(r.id)} className="text-red-500 hover:text-red-700 text-sm">🗑️</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default AutoAssignRulesPage;
