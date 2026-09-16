import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { contractorsApi, type Contractor } from '../api/contractors';
import { ContractorFormModal } from '../components/ContractorFormModal';
import { showToast } from '../utils/toast';
import NotificationBell from '../components/NotificationBell';

export const ContractorsPage: React.FC = () => {
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const [contractors, setContractors] = useState<Contractor[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState<string>('');
  const [showForm, setShowForm] = useState(false);
  const [editingContract, setEditingContract] = useState<Contractor | null>(null);

  useEffect(() => {
    loadContractors();
  }, []);

  const loadContractors = async () => {
    try {
      setLoading(true);
      const data = await contractorsApi.getAll();
      setContractors(data);
    } catch (err) {
      showToast.error('Не удалось загрузить контрагентов');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = () => {
    setEditingContract(null);
    setShowForm(true);
  };

  const handleEdit = (contractor: Contractor) => {
    setEditingContract(contractor);
    setShowForm(true);
  };

  const handleSave = async (data: any) => {
    try {
      if (editingContract) {
        await contractorsApi.update(editingContract.id, data);
        showToast.success('Контрагент обновлён');
      } else {
        await contractorsApi.create(data);
        showToast.success('Контрагент создан');
      }
      setShowForm(false);
      loadContractors();
    } catch (err: any) {
      showToast.error('Ошибка: ' + (err?.response?.data?.detail || err.message));
    }
  };

  const handleToggleActive = async (contractor: Contractor) => {
    try {
      await contractorsApi.update(contractor.id, { is_active: !contractor.is_active });
      showToast.success(
        contractor.is_active ? 'Контрагент деактивирован' : 'Контрагент активирован'
      );
      loadContractors();
    } catch (err) {
      showToast.error('Ошибка обновления');
    }
  };

  const filteredContractors = contractors.filter((c) => {
    const matchesSearch =
      c.name.toLowerCase().includes(search.toLowerCase()) ||
      c.inn?.toLowerCase().includes(search.toLowerCase());
    const matchesType = !typeFilter || c.type === typeFilter;
    return matchesSearch && matchesType;
  });

  const getTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      client: 'Клиент',
      owner: 'Собственник',
      subcontractor: 'Субподрядчик',
    };
    return labels[type] || type;
  };

  const getTypeColor = (type: string) => {
    const colors: Record<string, string> = {
      client: 'bg-blue-100 text-blue-800',
      owner: 'bg-green-100 text-green-800',
      subcontractor: 'bg-purple-100 text-purple-800',
    };
    return colors[type] || 'bg-gray-100 text-gray-800';
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
      <nav className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center space-x-6">
              <h1 className="text-xl font-bold text-gray-900">🚜 СпецТехника Про</h1>
              <button onClick={() => navigate('/')} className="text-gray-600 hover:text-gray-900">
                Dashboard
              </button>
            </div>
            <div className="flex items-center space-x-4">
              <span className="text-gray-700">{user?.email}</span>
              <NotificationBell />
              <button
                onClick={() => {
                  logout();
                  navigate('/login');
                }}
                className="bg-red-600 text-white px-4 py-2 rounded hover:bg-red-700"
              >
                Выйти
              </button>
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto py-8 px-4">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex justify-between items-center mb-6">
            <h1 className="text-2xl font-bold text-gray-900">👥 Контрагенты</h1>
            <button
              onClick={handleCreate}
              className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
            >
              + Добавить контрагента
            </button>
          </div>

          {/* Filters */}
          <div className="flex gap-4 mb-6">
            <input
              type="text"
              placeholder="Поиск по названию или ИНН..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="flex-1 px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
            />
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
            >
              <option value="">Все типы</option>
              <option value="client">Клиенты</option>
              <option value="owner">Собственники</option>
              <option value="subcontractor">Субподрядчики</option>
            </select>
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Название
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Тип
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    ИНН
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Контакты
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Налоги
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Статус
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Действия
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {filteredContractors.map((contractor) => (
                  <tr key={contractor.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-900">{contractor.name}</div>
                      {contractor.legal_address && (
                        <div className="text-xs text-gray-500 mt-1">
                          {contractor.legal_address.substring(0, 50)}...
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-1 text-xs font-medium rounded ${getTypeColor(
                          contractor.type
                        )}`}
                      >
                        {getTypeLabel(contractor.type)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900">{contractor.inn || '—'}</td>
                    <td className="px-4 py-3 text-sm text-gray-900">
                      {contractor.contact_name && <div>{contractor.contact_name}</div>}
                      {contractor.contact_phone && (
                        <div className="text-xs text-gray-500">{contractor.contact_phone}</div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900">
                      {contractor.tax_system ? (
                        <span className="text-xs bg-gray-100 px-2 py-1 rounded">
                          {contractor.tax_system.toUpperCase()}
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-1 text-xs font-medium rounded ${
                          contractor.is_active
                            ? 'bg-green-100 text-green-800'
                            : 'bg-red-100 text-red-800'
                        }`}
                      >
                        {contractor.is_active ? 'Активен' : 'Неактивен'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex justify-end gap-2">
                        <button
                          onClick={() => handleEdit(contractor)}
                          className="text-blue-600 hover:text-blue-900 text-sm"
                        >
                          Редактировать
                        </button>
                        <button
                          onClick={() => handleToggleActive(contractor)}
                          className={`text-sm ${
                            contractor.is_active
                              ? 'text-orange-600 hover:text-orange-900'
                              : 'text-green-600 hover:text-green-900'
                          }`}
                        >
                          {contractor.is_active ? 'Деактивировать' : 'Активировать'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {filteredContractors.length === 0 && (
            <div className="text-center py-12">
              <div className="text-5xl mb-4">👥</div>
              <p className="text-gray-600">Контрагенты не найдены</p>
            </div>
          )}
        </div>
      </main>

      {showForm && (
        <ContractorFormModal
          contractor={editingContract}
          onClose={() => setShowForm(false)}
          onSave={handleSave}
        />
      )}
    </div>
  );
};

export default ContractorsPage;
