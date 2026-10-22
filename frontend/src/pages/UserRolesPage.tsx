import React, { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import apiClient from '../api/client';

const UserRolesPage: React.FC = () => {
  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [selectedRole, setSelectedRole] = useState('');
  const [selectedUsers, setSelectedUsers] = useState<Set<number>>(new Set());
  const [bulkRole, setBulkRole] = useState('');
  const [csvFile, setCsvFile] = useState<File | null>(null);

  const roles = [
    { value: 'admin', label: '👑 Админ', color: 'bg-purple-100 text-purple-700' },
    { value: 'dispatcher', label: '📋 Диспетчер', color: 'bg-blue-100 text-blue-700' },
    { value: 'driver', label: '🚗 Водитель', color: 'bg-green-100 text-green-700' },
    { value: 'accountant', label: '💰 Бухгалтер', color: 'bg-orange-100 text-orange-700' },
    { value: 'viewer', label: '👁️ Наблюдатель', color: 'bg-gray-100 text-gray-700' },
  ];

  const toggleUser = (id: number) => {
    const next = new Set(selectedUsers);
    if (next.has(id)) next.delete(id); else next.add(id);
    setSelectedUsers(next);
  };

  const bulkChangeRole = async () => {
    if (!bulkRole || selectedUsers.size === 0) return;
    try {
      const res = await apiClient.put('/shifts/users/bulk-role', { user_ids: Array.from(selectedUsers), role: bulkRole });
      alert(`✅ Обновлено ${res.data.updated} пользователей`);
      setSelectedUsers(new Set());
      loadUsers();
    } catch (err: any) { alert('Ошибка: ' + (err.response?.data?.detail || '')); }
  };

  const importCsv = async () => {
    if (!csvFile) return;
    const formData = new FormData();
    formData.append('file', csvFile);
    formData.append('default_role', 'viewer');
    try {
      const res = await apiClient.post('/shifts/users/import-csv', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
      alert(`✅ Создано: ${res.data.created}, Пропущено: ${res.data.skipped}`);
      setCsvFile(null);
      loadUsers();
    } catch (err: any) { alert('Ошибка: ' + (err.response?.data?.detail || '')); }
  };

  const loadUsers = async () => {
    try {
      const res = await apiClient.get('/shifts/users/roles');
      setUsers(Array.isArray(res.data) ? res.data : []);
    } catch {} finally { setLoading(false); }
  };

  useEffect(() => { loadUsers(); }, []);

  const saveRole = async (userId: number) => {
    if (!selectedRole) return;
    try {
      const res = await apiClient.put(`/shifts/users/${userId}/role`, { role: selectedRole });
      alert(`✅ ${res.data.message}`);
      setEditingId(null);
      loadUsers();
    } catch (err: any) { alert('Ошибка: ' + (err.response?.data?.detail || '')); }
  };

  const getRoleBadge = (role: string) => {
    const r = roles.find(x => x.value === role);
    return r ? <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${r.color}`}>{r.label}</span>
      : <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">{role}</span>;
  };

  return (
    <Layout>
      <div className="p-6 space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">🔑 Управление ролями</h1>

        {loading ? (
          <div className="flex justify-center py-12"><div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600"></div></div>
        ) : (
          <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Пользователь</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Email</th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Роль</th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Статус</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Действия</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {users.map((u: any) => (
                  <tr key={u.id} className={`hover:bg-gray-50 ${selectedUsers.has(u.id) ? 'bg-indigo-50' : ''}`}>
                    <td className="px-4 py-3 text-center"><input type="checkbox" checked={selectedUsers.has(u.id)} onChange={() => toggleUser(u.id)} /></td>
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">
                      {u.full_name || '—'}
                      {u.is_superuser && <span className="ml-1 text-xs text-purple-500">★</span>}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">{u.email}</td>
                    <td className="px-4 py-3 text-center">
                      {editingId === u.id ? (
                        <select value={selectedRole} onChange={e => setSelectedRole(e.target.value)}
                          className="px-2 py-1 border rounded text-sm w-36">
                          {roles.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
                        </select>
                      ) : getRoleBadge(u.role)}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className={`px-2 py-0.5 rounded-full text-xs ${u.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                        {u.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      {editingId === u.id ? (
                        <div className="flex gap-1 justify-end">
                          <button onClick={() => saveRole(u.id)} className="px-2 py-1 bg-green-600 text-white rounded text-xs font-medium">✅</button>
                          <button onClick={() => setEditingId(null)} className="px-2 py-1 bg-gray-200 text-gray-600 rounded text-xs font-medium">✕</button>
                        </div>
                      ) : (
                        <button onClick={() => { setEditingId(u.id); setSelectedRole(u.role); }}
                          className="px-2 py-1 bg-indigo-100 text-indigo-700 rounded text-xs font-medium hover:bg-indigo-200">
                          ✏️ Изменить
                        </button>
                      )}
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

export default UserRolesPage;
