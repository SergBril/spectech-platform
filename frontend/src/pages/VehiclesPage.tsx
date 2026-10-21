import React, { useEffect, useState, useRef, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { vehiclesApi } from '../api/vehicles';
import type { Vehicle } from '../api/vehicles';
import { useAuth } from '../contexts/AuthContext';
import { VehicleFormModal } from '../components/VehicleFormModal';
import DeleteConfirmDialog from '../components/DeleteConfirmDialog';
import Layout from '../components/Layout';
import apiClient from '../api/client';

interface Driver {
  id: number;
  full_name: string;
  is_assigned?: boolean;
}

const ALL_COLS = [
  { key: 'id', label: 'ID', def: 60 },
  { key: 'name', label: 'Название', def: 180 },
  { key: 'id_value', label: 'Номер', def: 120 },
  { key: 'category', label: 'Категория', def: 150 },
  { key: 'subcategory', label: 'Подкатегория', def: 150 },
  { key: 'make_model', label: 'Марка/Модель', def: 160 },
  { key: 'year', label: 'Год', def: 70 },
  { key: 'driver', label: 'Водитель', def: 180 },
  { key: 'status', label: 'Статус', def: 100 },
];

export const VehiclesPage: React.FC = () => {
  const { hasPermission } = useAuth();
  const canCreate = hasPermission('vehicles', 'create');
  const canEditVehicle = hasPermission('vehicles', 'update');
  const canDeleteVehicle = hasPermission('vehicles', 'delete');
  const navigate = useNavigate();

  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [drivers, setDrivers] = useState<Driver[]>([]);

  const [showFormModal, setShowFormModal] = useState(false);
  const [editingVehicle, setEditingVehicle] = useState<Vehicle | null>(null);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [deletingVehicle, setDeletingVehicle] = useState<Vehicle | null>(null);

  // Sorting
  const [sortBy, setSortBy] = useState<string>('id');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');

  // Pagination
  const [page, setPage] = useState(1);
  const perPage = 25;

  // Resizable + Visibility
  const [colWidths, setColWidths] = useState<Record<string, number>>({});
  const resizingRef = useRef<{ key: string; startX: number; startW: number } | null>(null);
  const [visibleCols, setVisibleCols] = useState<Record<string, boolean>>({});
  const [showColMenu, setShowColMenu] = useState(false);
  const colMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    try { const s = localStorage.getItem('veh_col_w'); if (s) setColWidths(JSON.parse(s)); } catch {}
    try { const v = localStorage.getItem('veh_vis_cols'); if (v) { setVisibleCols(JSON.parse(v)); return; } } catch {}
    const d: Record<string, boolean> = {};
    ALL_COLS.forEach(c => { d[c.key] = true; });
    setVisibleCols(d);
  }, []);

  useEffect(() => { try { localStorage.setItem('veh_col_w', JSON.stringify(colWidths)); } catch {} }, [colWidths]);
  useEffect(() => { if (Object.keys(visibleCols).length > 0) try { localStorage.setItem('veh_vis_cols', JSON.stringify(visibleCols)); } catch {} }, [visibleCols]);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!resizingRef.current) return;
      const diff = e.clientX - resizingRef.current.startX;
      const nw = Math.max(50, resizingRef.current.startW + diff);
      setColWidths(prev => ({ ...prev, [resizingRef.current!.key]: nw }));
    };
    const onUp = () => {
      if (resizingRef.current) { resizingRef.current = null; document.body.style.cursor = ''; document.body.style.userSelect = ''; }
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
  }, []);

  useEffect(() => {
    const handler = (e: MouseEvent) => { if (colMenuRef.current && !colMenuRef.current.contains(e.target as Node)) setShowColMenu(false); };
    if (showColMenu) document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showColMenu]);

  const colSt = (key: string, def: number) => { const w = colWidths[key]; return w ? { width: w + 'px', minWidth: w + 'px' } : { minWidth: def + 'px' }; };
  const isVis = (key: string) => visibleCols[key] === undefined ? true : visibleCols[key] !== false;
  const toggleVis = (key: string) => setVisibleCols(p => ({ ...p, [key]: !isVis(key) }));
  const onMouseDownResize = (e: React.MouseEvent, colKey: string, defaultW: number) => {
    e.preventDefault(); e.stopPropagation();
    resizingRef.current = { key: colKey, startX: e.clientX, startW: colWidths[colKey] || defaultW };
    document.body.style.cursor = 'col-resize'; document.body.style.userSelect = 'none';
  };

  const handleSort = (key: string) => {
    if (sortBy === key) { setSortOrder(o => o === 'asc' ? 'desc' : 'asc'); }
    else { setSortBy(key); setSortOrder('asc'); }
  };

  const sortIndicator = (key: string) => {
    if (sortBy !== key) return <span className="text-gray-300 ml-1">↕</span>;
    return <span className="ml-1">{sortOrder === 'asc' ? '↑' : '↓'}</span>;
  };

  // Load data
  const loadVehicles = async () => {
    try {
      setIsLoading(true);
      const response = await vehiclesApi.list({ sort_by: sortBy, sort_order: sortOrder, skip: (page - 1) * perPage, limit: perPage } as any);
      setVehicles(response.items);
      setTotal(response.total);
      setError('');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Ошибка загрузки техники');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => { loadVehicles(); }, [sortBy, sortOrder, page]);

  useEffect(() => { loadDrivers(); }, []);

  const handleCreate = () => { setEditingVehicle(null); setShowFormModal(true); };
  const handleEdit = (vehicle: Vehicle) => { setEditingVehicle(vehicle); setShowFormModal(true); };
  const handleDelete = (vehicle: Vehicle) => { setDeletingVehicle(vehicle); setShowDeleteDialog(true); };
  const handleFormClose = () => { setShowFormModal(false); setEditingVehicle(null); loadVehicles(); };

  const handleDeleteConfirm = async () => {
    if (!deletingVehicle) return;
    try {
      await vehiclesApi.delete(deletingVehicle.id);
      setShowDeleteDialog(false); setDeletingVehicle(null); loadVehicles();
    } catch (err: any) { alert(err.response?.data?.detail || 'Ошибка удаления'); }
  };

  const loadDrivers = async () => {
    try {
      const r = await apiClient.get('/vehicles/drivers?limit=500');
      const items = Array.isArray(r.data) ? r.data : r.data?.items || [];
      setDrivers(items.map((d: any) => ({ id: d.id, full_name: d.full_name || d.name || `#${d.id}`, is_assigned: d.is_assigned || false })));
    } catch {}
  };

  const handleDriverChange = async (vehicleId: number, driverId: string) => {
    try {
      const newDriverId = driverId ? parseInt(driverId) : null;
      await vehiclesApi.update(vehicleId, { assigned_driver_id: newDriverId });
      // Reload both vehicles and drivers to reflect unique assignment
      await Promise.all([loadVehicles(), loadDrivers()]);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Ошибка назначения водителя');
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'free': return 'bg-green-100 text-green-800';
      case 'busy': return 'bg-red-100 text-red-800';
      case 'maintenance': return 'bg-yellow-100 text-yellow-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'free': return 'Свободна';
      case 'busy': return 'Занята';
      case 'maintenance': return 'ТО';
      default: return status;
    }
  };

  const sortedVehicles = useMemo(() => {
    const arr = [...vehicles];
    arr.sort((a: any, b: any) => {
      let va = a[sortBy] ?? '';
      let vb = b[sortBy] ?? '';
      if (sortBy === 'category') { va = a.category_name ?? ''; vb = b.category_name ?? ''; }
      if (sortBy === 'subcategory') { va = a.subcategory_name ?? ''; vb = b.subcategory_name ?? ''; }
      if (sortBy === 'make_model') { va = [a.make, a.model].filter(Boolean).join(' '); vb = [b.make, b.model].filter(Boolean).join(' '); }
      if (typeof va === 'string') va = va.toLowerCase();
      if (typeof vb === 'string') vb = vb.toLowerCase();
      if (va < vb) return sortOrder === 'asc' ? -1 : 1;
      if (va > vb) return sortOrder === 'asc' ? 1 : -1;
      return 0;
    });
    return arr;
  }, [vehicles, sortBy, sortOrder]);

  const ThCell = ({ colKey, label, def }: { colKey: string; label: string; def: number }) => (
    <th
      className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase whitespace-nowrap relative group select-none cursor-pointer hover:bg-gray-100"
      style={colSt(colKey, def)}
      onClick={() => handleSort(colKey)}
    >
      {label}{sortIndicator(colKey)}
      <div
        className="absolute right-0 top-0 bottom-0 w-[3px] cursor-col-resize bg-gray-200 hover:bg-blue-500 transition-colors"
        onMouseDown={(e) => onMouseDownResize(e, colKey, def)}
      />
    </th>
  );

  return (
    <Layout>
      <div className="px-4 py-6 sm:px-0">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-2xl font-bold text-gray-900">
            Список техники ({total})
          </h2>
          <div className="flex gap-2">
            <div className="relative" ref={colMenuRef}>
              <button onClick={() => setShowColMenu(!showColMenu)}
                className="bg-gray-100 text-gray-700 px-3 py-2 rounded hover:bg-gray-200 flex items-center shadow-sm text-sm"
                title="Настройка столбцов">⚙️ Столбцы</button>
              {showColMenu && (
                <div className="absolute right-0 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-xl z-50 py-2 min-w-[200px]">
                  <div className="px-3 py-1 text-xs font-semibold text-gray-500 uppercase">Видимость столбцов</div>
                  {ALL_COLS.map(col => (
                    <label key={col.key} className="flex items-center gap-2 px-3 py-1.5 hover:bg-gray-50 cursor-pointer text-sm">
                      <input type="checkbox" checked={isVis(col.key)} onChange={() => toggleVis(col.key)}
                        className="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
                      {col.label}
                    </label>
                  ))}
                  <div className="border-t border-gray-100 mt-1 pt-1 px-3">
                    <button onClick={() => { const a: Record<string, boolean> = {}; ALL_COLS.forEach(c => { a[c.key] = true; }); setVisibleCols(a); }}
                      className="text-xs text-blue-600 hover:text-blue-800">Показать все</button>
                  </div>
                </div>
              )}
            </div>
            {canCreate && (
              <button onClick={handleCreate}
                className="bg-blue-600 text-white px-6 py-2 rounded hover:bg-blue-700 flex items-center shadow-sm">
                <span className="mr-2">+</span> Создать технику
              </button>
            )}
          </div>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">{error}</div>
        )}

        {isLoading ? (
          <div className="text-center py-12 text-gray-500">Загрузка...</div>
        ) : vehicles.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            Техника не найдена. {canCreate && 'Создайте первую запись!'}
          </div>
        ) : (
          <div className="bg-white shadow rounded-lg overflow-hidden">
            <div className="overflow-x-auto overflow-y-auto max-h-[70vh] border border-gray-200 rounded">
            <table className="min-w-[1400px] w-full divide-y divide-gray-200">
                <thead className="bg-gray-50 sticky top-0 z-10 shadow-sm">
                  <tr>
                    {isVis('id') && <ThCell colKey="id" label="ID" def={60} />}
                    {isVis('name') && <ThCell colKey="name" label="Название" def={180} />}
                    {isVis('id_value') && <ThCell colKey="id_value" label="Номер" def={120} />}
                    {isVis('category') && <ThCell colKey="category" label="Категория" def={150} />}
                    {isVis('subcategory') && <ThCell colKey="subcategory" label="Подкатегория" def={150} />}
                    {isVis('make_model') && <ThCell colKey="make_model" label="Марка/Модель" def={160} />}
                    {isVis('year') && <ThCell colKey="year" label="Год" def={70} />}
                    {isVis('driver') && <ThCell colKey="driver" label="Водитель" def={180} />}
                    {isVis('status') && <ThCell colKey="status" label="Статус" def={100} />}
                    {(canEditVehicle || canDeleteVehicle) && (
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase" style={{ minWidth: '120px' }}>Действия</th>
                    )}
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {sortedVehicles.map((vehicle) => (
                    <tr
                      key={vehicle.id}
                      onClick={() => canEditVehicle && handleEdit(vehicle)}
                      className={`transition-colors ${canEditVehicle ? 'hover:bg-blue-50 cursor-pointer' : 'hover:bg-gray-50'}`}
                    >
                      {isVis('id') && (
                        <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-500">{vehicle.id}</td>
                      )}
                      {isVis('name') && (
                        <td className="px-4 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{vehicle.name}</td>
                      )}
                      {isVis('id_value') && (
                        <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-500">{vehicle.id_value}</td>
                      )}
                      {isVis('category') && (
                        <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-500">{(vehicle as any).category_name || '-'}</td>
                      )}
                      {isVis('subcategory') && (
                        <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-500">{(vehicle as any).subcategory_name || '-'}</td>
                      )}
                      {isVis('make_model') && (
                        <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
                          {[(vehicle as any).make, (vehicle as any).model].filter(Boolean).join(' ') || '-'}
                        </td>
                      )}
                      {isVis('year') && (
                        <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-500">{vehicle.year || '-'}</td>
                      )}
                      {isVis('driver') && (
                        <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-700" onClick={(e) => e.stopPropagation()}>
                          {canEditVehicle ? (
                            <select
                              value={(vehicle as any).assigned_driver_id || ''}
                              onChange={(e) => handleDriverChange(vehicle.id, e.target.value)}
                              className="w-full max-w-[160px] px-2 py-1 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                            >
                              <option value="">— Не назначен —</option>
                              {drivers.filter(d => !d.is_assigned || d.id === ((vehicle as any).assigned_driver_id)).map(d => (
                                <option key={d.id} value={d.id}>{d.full_name}{d.is_assigned && d.id !== (vehicle as any).assigned_driver_id ? ' (занят)' : ''}</option>
                              ))}
                            </select>
                          ) : (
                            ((vehicle as any).assigned_driver_name || <span className="text-gray-400">—</span>)
                          )}
                        </td>
                      )}
                      {isVis('status') && (
                        <td className="px-4 py-4 whitespace-nowrap">
                          <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusColor(vehicle.status)}`}>
                            {getStatusLabel(vehicle.status)}
                          </span>
                        </td>
                      )}
                      {(canEditVehicle || canDeleteVehicle) && (
                        <td className="px-4 py-4 whitespace-nowrap text-right text-sm font-medium">
                          <div className="flex justify-end space-x-2">
                            {canEditVehicle && (
                              <button onClick={(e) => { e.stopPropagation(); handleEdit(vehicle); }}
                                className="text-blue-600 hover:text-blue-900">✏️</button>
                            )}
                            {canDeleteVehicle && (
                              <button onClick={(e) => { e.stopPropagation(); handleDelete(vehicle); }}
                                className="text-red-600 hover:text-red-900">🗑️</button>
                            )}
                          </div>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {showFormModal && (
        <VehicleFormModal vehicle={editingVehicle} onClose={handleFormClose} />
      )}

      {showDeleteDialog && deletingVehicle && (
        <DeleteConfirmDialog
          title="Удалить технику?"
          message={`Техника "${deletingVehicle.name}" будет удалена безвозвратно.`}
          onConfirm={handleDeleteConfirm}
          onCancel={() => { setShowDeleteDialog(false); setDeletingVehicle(null); }}
        />
      )}
    </Layout>
  );
};

export default VehiclesPage;
