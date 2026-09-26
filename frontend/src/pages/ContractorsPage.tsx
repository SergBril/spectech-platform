import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { contractorsApi, type Contractor } from '../api/contractors';
import { ContractorFormModal } from '../components/ContractorFormModal';
import { showToast } from '../utils/toast';
import Navbar from '../components/Navbar';

export const ContractorsPage: React.FC = () => {
  const navigate = useNavigate();
  const { hasPermission } = useAuth();

  const [contractors, setContractors] = useState<Contractor[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [taxFilter, setTaxFilter] = useState<string>('all');
  const [showForm, setShowForm] = useState(false);
  const [editingContract, setEditingContract] = useState<Contractor | null>(null);

  const canCreate = hasPermission('contractors', 'create');
  const canEdit = hasPermission('contractors', 'update');

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

  const handleEdit = (e: React.MouseEvent, contractor: Contractor) => {
    e.stopPropagation();
    setEditingContract(contractor);
    setShowForm(true);
  };

  const handleRowClick = (contractor: Contractor) => {
    navigate(`/contractors/${contractor.id}`);
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

  const handleToggleActive = async (e: React.MouseEvent, contractor: Contractor) => {
    e.stopPropagation();
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

  // 🆕 Фильтрация с useMemo
  const filteredContractors = useMemo(() => {
    return contractors.filter((c) => {
      const q = search.toLowerCase();
      const matchesSearch =
        !search ||
        c.name.toLowerCase().includes(q) ||
        c.inn?.toLowerCase().includes(q) ||
        c.contact_email?.toLowerCase().includes(q);
      const matchesType = typeFilter === 'all' || c.type === typeFilter;
      const matchesTax = taxFilter === 'all' || c.tax_system === taxFilter;
      return matchesSearch && matchesType && matchesTax;
    });
  }, [contractors, search, typeFilter, taxFilter]);

  // Подсчёт статистики для фильтров
  const typeCounts = useMemo(() => {
    const counts: Record<string, number> = { all: contractors.length };
    contractors.forEach(c => {
      counts[c.type] = (counts[c.type] || 0) + 1;
    });
    return counts;
  }, [contractors]);

  const getTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      client: '👤 Клиент',
      owner: '🚜 Собственник',
      subcontractor: '🤝 Субподрядчик',
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

  const getTaxLabel = (taxSystem: string | undefined) => {
    const labels: Record<string, string> = {
      osno: 'ОСНО',
      usn_6: 'УСН 6%',
      usn_15: 'УСН 15%',
      patent: 'Патент',
      npd: 'НПД',
    };
    return labels[taxSystem || ''] || '—';
  };

  const getTaxColor = (taxSystem: string | undefined) => {
    const colors: Record<string, string> = {
      osno: 'bg-indigo-100 text-indigo-800',
      usn_6: 'bg-teal-100 text-teal-800',
      usn_15: 'bg-cyan-100 text-cyan-800',
      patent: 'bg-amber-100 text-amber-800',
      npd: 'bg-emerald-100 text-emerald-800',
    };
    return colors[taxSystem || ''] || 'bg-gray-100 text-gray-800';
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
      <Navbar />

      <main className="max-w-7xl mx-auto py-8 px-4">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex justify-between items-center mb-6">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">👥 Контрагенты</h1>
              <p className="text-sm text-gray-600 mt-1">
                Всего: <strong>{filteredContractors.length}</strong>
                {filteredContractors.length !== contractors.length && (
                  <span className="text-gray-500"> из {contractors.length}</span>
                )}
              </p>
            </div>
            {canCreate && (
              <button
                onClick={handleCreate}
                className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
              >
                + Добавить контрагента
              </button>
            )}
          </div>

          {/* 🆕 Фильтры */}
          <div className="flex flex-wrap gap-3 mb-6 p-4 bg-gray-50 rounded-lg">
            <div className="flex-1 min-w-[250px]">
              <input
                type="text"
                placeholder="🔍 Поиск по названию, ИНН, email..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
              />
            </div>
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
            >
              <option value="all">Все типы ({typeCounts.all})</option>
              <option value="client">👤 Клиенты ({typeCounts.client || 0})</option>
              <option value="owner">🚜 Собственники ({typeCounts.owner || 0})</option>
              <option value="subcontractor">🤝 Субподрядчики ({typeCounts.subcontractor || 0})</option>
            </select>
            <select
              value={taxFilter}
              onChange={(e) => setTaxFilter(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
            >
              <option value="all">Все налоги</option>
              <option value="osno">ОСНО (с НДС)</option>
              <option value="usn_6">УСН 6%</option>
              <option value="usn_15">УСН 15%</option>
              <option value="patent">Патент</option>
              <option value="npd">НПД</option>
            </select>
            {(search || typeFilter !== 'all' || taxFilter !== 'all') && (
              <button
                onClick={() => { setSearch(''); setTypeFilter('all'); setTaxFilter('all'); }}
                className="px-3 py-2 text-sm text-gray-600 hover:text-gray-900"
              >
                ✕ Сбросить
              </button>
            )}
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
                    ИНН / КПП
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
                  {canEdit && (
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                      Действия
                    </th>
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {filteredContractors.map((contractor) => (
                  <tr
                    key={contractor.id}
                    onClick={() => handleRowClick(contractor)}
                    className="hover:bg-blue-50 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3">
                      <div className="font-medium text-blue-600">{contractor.name}</div>
                      {contractor.legal_address && (
                        <div className="text-xs text-gray-500 mt-1 max-w-xs truncate">
                          📍 {contractor.legal_address}
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
                    <td className="px-4 py-3 text-sm text-gray-900">
                      <div className="font-mono">{contractor.inn || '—'}</div>
                      {contractor.kpp && (
                        <div className="text-xs text-gray-500 font-mono">{contractor.kpp}</div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900">
                      {contractor.contact_name && (
                        <div className="text-xs">👤 {contractor.contact_name}</div>
                      )}
                      {contractor.contact_phone && (
                        <div className="text-xs">📞 {contractor.contact_phone}</div>
                      )}
                      {contractor.contact_email && (
                        <div className="text-xs text-blue-600">✉️ {contractor.contact_email}</div>
                      )}
                      {!contractor.contact_name && !contractor.contact_phone && !contractor.contact_email && '—'}
                    </td>
                    <td className="px-4 py-3">
                      {contractor.tax_system ? (
                        <span className={`px-2 py-1 text-xs font-semibold rounded ${getTaxColor(contractor.tax_system)}`}>
                          {getTaxLabel(contractor.tax_system)}
                        </span>
                      ) : (
                        <span className="text-gray-400 text-xs">—</span>
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
                        {contractor.is_active ? '✅ Активен' : '❌ Неактивен'}
                      </span>
                    </td>
                    {canEdit && (
                      <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                        <div className="flex justify-end gap-2">
                          <button
                            onClick={(e) => handleEdit(e, contractor)}
                            className="text-blue-600 hover:text-blue-900 text-sm"
                            title="Редактировать"
                          >
                            ✏️
                          </button>
                          <button
                            onClick={(e) => handleToggleActive(e, contractor)}
                            className={`text-sm ${
                              contractor.is_active
                                ? 'text-orange-600 hover:text-orange-900'
                                : 'text-green-600 hover:text-green-900'
                            }`}
                            title={contractor.is_active ? 'Деактивировать' : 'Активировать'}
                          >
                            {contractor.is_active ? '🚫' : '✅'}
                          </button>
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {filteredContractors.length === 0 && (
            <div className="text-center py-12">
              <div className="text-5xl mb-4">👥</div>
              <p className="text-gray-600">
                {contractors.length === 0 ? 'Контрагентов пока нет' : 'Контрагенты не найдены по фильтрам'}
              </p>
              {canCreate && contractors.length === 0 && (
                <button
                  onClick={handleCreate}
                  className="mt-4 bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
                >
                  + Добавить первого контрагента
                </button>
              )}
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
