import React, { useEffect, useState, useMemo, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { requestsApi, type Request, type RequestStatus } from '../api/requests';
import apiClient from '../api/client';
import { TableSkeleton } from '../components/Skeleton';
import RequestFormModal from '../components/RequestFormModal';
import DeleteConfirmDialog from '../components/DeleteConfirmDialog';
import Layout from '../components/Layout';

const STATUS_LABELS: Record<RequestStatus, { label: string; color: string }> = {
  new: { label: 'Новая', color: 'bg-blue-100 text-blue-800' },
  processing: { label: 'В обработке', color: 'bg-yellow-100 text-yellow-800' },
  assigned: { label: 'Назначена', color: 'bg-indigo-100 text-indigo-800' },
  confirmed: { label: 'Подтверждена', color: 'bg-green-100 text-green-800' },
  released: { label: 'Выпущена', color: 'bg-purple-100 text-purple-800' },
  in_progress: { label: 'В работе', color: 'bg-cyan-100 text-cyan-800' },
  completed: { label: 'Завершена', color: 'bg-emerald-100 text-emerald-800' },
  signed: { label: 'Подписана', color: 'bg-teal-100 text-teal-800' },
  closed: { label: 'Закрыта', color: 'bg-gray-100 text-gray-800' },
  cancelled: { label: 'Отменена', color: 'bg-red-100 text-red-800' },
  disputed: { label: 'Спорная', color: 'bg-orange-100 text-orange-800' },
};

const PRIORITY_LABELS: Record<string, { label: string; color: string }> = {
  low: { label: 'Низкий', color: 'text-gray-600' },
  normal: { label: 'Обычный', color: 'text-blue-600' },
  high: { label: 'Высокий', color: 'text-orange-600' },
  urgent: { label: 'Срочный', color: 'text-red-600 font-semibold' },
};

const formatDateTime = (dt: string | null) => {
  if (!dt) return '—';
  return new Date(dt).toLocaleString('ru-RU', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit'
  });
};

const formatDate = (dt: string | null) => {
  if (!dt) return '—';
  return new Date(dt).toLocaleDateString('ru-RU', {
    day: '2-digit', month: '2-digit', year: 'numeric',
  });
};

const formatMoney = (v: number | string | null | undefined) => {
  if (v === null || v === undefined || v === '') return '—';
  const num = typeof v === 'string' ? parseFloat(v) : v;
  return `${num.toLocaleString('ru-RU')} ₽`;
};


const downloadFile = async (fn: (p: any) => Promise<Blob>, filename: string, params: any) => {
  try {
    const blob = await fn(params);
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  } catch (err) {
    console.error('Export failed:', err);
    alert('Ошибка при экспорте');
  }
};

export const RequestsPage: React.FC = () => {
  const { user, hasPermission } = useAuth();
  const navigate = useNavigate();

  const [requests, setRequests] = useState<Request[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [filterPriority, setFilterPriority] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [filterCategory, setFilterCategory] = useState<string>('all');
  const [filterVehicleId, setFilterVehicleId] = useState<string>('all');
  const [filterDateFrom, setFilterDateFrom] = useState('');
  const [filterDateTo, setFilterDateTo] = useState('');
  const [sortBy, setSortBy] = useState('created_at');
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [categories, setCategories] = useState<{id:number;name:string}[]>([]);
  const [vehicles, setVehicles] = useState<{id:number;name:string}[]>([]);

  // === Resizable + Visibility ===
  const [colWidths, setColWidths] = useState<Record<string, number>>({});
  const resizingRef = useRef<{key: string; startX: number; startW: number} | null>(null);
  const ALL_COLS = [
    { key: 'id', label: '№' }, { key: 'work_type', label: 'Тип работы' },
    { key: 'address', label: 'Адрес' }, { key: 'period', label: 'Период' },
    { key: 'category', label: 'Категория' }, { key: 'vehicle', label: 'Техника' },
    { key: 'client', label: 'Клиент' }, { key: 'status', label: 'Статус' },
    { key: 'priority', label: 'Приоритет' }, { key: 'amount', label: 'Сумма' },
  ];
  const [visibleCols, setVisibleCols] = useState<Record<string, boolean>>({});
  const [showColMenu, setShowColMenu] = useState(false);
  const colMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    try { const s = localStorage.getItem('req_col_w'); if (s) setColWidths(JSON.parse(s)); } catch {}
    try { const v = localStorage.getItem('req_vis_cols'); if (v) { setVisibleCols(JSON.parse(v)); return; } } catch {}
    const d: Record<string, boolean> = {};
    ALL_COLS.forEach(c => { d[c.key] = true; });
    setVisibleCols(d);
  }, []);

  useEffect(() => {
    try { localStorage.setItem('req_col_w', JSON.stringify(colWidths)); } catch {}
  }, [colWidths]);

  useEffect(() => {
    if (Object.keys(visibleCols).length > 0)
      try { localStorage.setItem('req_vis_cols', JSON.stringify(visibleCols)); } catch {}
  }, [visibleCols]);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!resizingRef.current) return;
      const diff = e.clientX - resizingRef.current.startX;
      const nw = Math.max(60, resizingRef.current.startW + diff);
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

  const colSt = (key: string, def: number) => { const w = colWidths[key]; return w ? { width: w+'px', minWidth: w+'px' } : { minWidth: def+'px' }; };
  const isVis = (key: string) => visibleCols[key] === undefined ? true : visibleCols[key] !== false;
  const toggleVis = (key: string) => setVisibleCols(p => ({ ...p, [key]: !isVis(key) }));
  const onMouseDownResize = (e: React.MouseEvent, colKey: string, defaultW: number) => {
    e.preventDefault(); e.stopPropagation();
    resizingRef.current = { key: colKey, startX: e.clientX, startW: colWidths[colKey] || defaultW };
    document.body.style.cursor = 'col-resize'; document.body.style.userSelect = 'none';
  };

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingRequest, setEditingRequest] = useState<Request | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Request | null>(null);

  const canCreate = hasPermission('requests', 'create');
  const canEdit = hasPermission('requests', 'update');
  const canDelete = hasPermission('requests', 'delete');
  const getExportParams = () => {
    const params: any = {};
    if (filterStatus !== 'all') params.status = filterStatus;
    if (filterPriority !== 'all') params.priority = filterPriority;
    if (debouncedSearch) params.search = debouncedSearch;
    if (filterCategory !== 'all') params.vehicle_category_id = parseInt(filterCategory);
    if (filterVehicleId !== 'all') params.assigned_vehicle_id = parseInt(filterVehicleId);
    if (filterDateFrom) params.date_from = filterDateFrom;
    if (filterDateTo) params.date_to = filterDateTo;
    params.sort_by = sortBy;
    params.sort_order = sortOrder;
    return params;
  };

  // Debounce поиска - ждем 300мс после ввода
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const loadRequests = async (showSkeleton = false) => {
    if (showSkeleton) setLoading(true);
    try {
      setLoading(true);
      const params: any = { limit: 200, sort_by: sortBy, sort_order: sortOrder };
      if (filterStatus !== 'all') params.status = filterStatus;
      if (filterPriority !== 'all') params.priority = filterPriority;
      if (debouncedSearch) params.search = debouncedSearch;
      if (filterCategory !== 'all') params.vehicle_category_id = parseInt(filterCategory);
      if (filterVehicleId !== 'all') params.assigned_vehicle_id = parseInt(filterVehicleId);
      if (filterDateFrom) params.date_from = filterDateFrom;
      if (filterDateTo) params.date_to = filterDateTo;
      const data = await requestsApi.getAll(params);
      setRequests(data);
      setError('');
    } catch (err: any) {
      console.error('Failed to load requests:', err);
      setError('Не удалось загрузить заявки');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    apiClient.get('/categories').then(r => setCategories(r.data)).catch(() => {});
    apiClient.get('/vehicles?limit=500').then(r => {
      const items = Array.isArray(r.data) ? r.data : r.data?.items || [];
      setVehicles(items.map((v: any) => ({ id: v.id, name: v.name || v.license_plate || `#${v.id}` })));
    }).catch(() => {});
  }, []);

  useEffect(() => {
    loadRequests(!isInitialLoading ? false : true);
    if (isInitialLoading) setIsInitialLoading(false);
  }, [filterStatus, filterPriority, debouncedSearch, filterCategory, filterVehicleId, filterDateFrom, filterDateTo, sortBy, sortOrder]);

  const filteredRequests = useMemo(() => {
    return requests.filter((req) => {
      if (filterStatus !== 'all' && req.status !== filterStatus) return false;
      if (filterPriority !== 'all' && req.priority !== filterPriority) return false;
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        const matchesSearch =
          req.work_type?.toLowerCase().includes(q) ||
          req.object_address?.toLowerCase().includes(q) ||
          String(req.id).includes(q) ||
          (req as any).client_name?.toLowerCase().includes(q);
        if (!matchesSearch) return false;
      }
      return true;
    });
  }, [requests, filterStatus, filterPriority, searchQuery]);

  const handleCreate = () => {
    setEditingRequest(null);
    setIsModalOpen(true);
  };

  const handleEdit = (e: React.MouseEvent, request: Request) => {
    e.stopPropagation();
    setEditingRequest(request);
    setIsModalOpen(true);
  };

  const handleDelete = (e: React.MouseEvent, request: Request) => {
    e.stopPropagation();
    setDeleteTarget(request);
  };

  const handleRowClick = (request: Request) => {
    navigate(`/requests/${request.id}`);
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    try {
      await requestsApi.delete(deleteTarget.id);
      setRequests(requests.filter(r => r.id !== deleteTarget.id));
      setDeleteTarget(null);
    } catch (err: any) {
      console.error('Failed to delete request:', err);
      alert('Ошибка при удалении заявки');
    }
  };

  const handleSave = async (data: any) => {
    try {
      if (editingRequest) {
        const updated = await requestsApi.update(editingRequest.id, data);
        setRequests(requests.map(r => r.id === editingRequest.id ? updated : r));
      } else {
        const created = await requestsApi.create(data);
        setRequests([created, ...requests]);
      }
      setIsModalOpen(false);
      setEditingRequest(null);
    } catch (err: any) {
      alert('Ошибка: ' + (err?.response?.data?.detail || err.message));
      throw err;
    }
  };

  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = { all: requests.length };
    requests.forEach(r => {
      counts[r.status] = (counts[r.status] || 0) + 1;
    });
    return counts;
  }, [requests]);

  if (isInitialLoading && loading) {
    return (
      <Layout>
        <div className="px-4 py-6 sm:px-0">
          <div className="flex justify-between items-center mb-6">
            <div className="w-40 h-8 bg-gray-200 rounded animate-pulse" />
            <div className="w-40 h-10 bg-gray-200 rounded animate-pulse" />
          </div>
          <div className="bg-white rounded-lg shadow p-4 mb-6 animate-pulse">
            <div className="flex flex-wrap gap-3">
              <div className="w-48 h-10 bg-gray-100 rounded" />
              <div className="w-40 h-10 bg-gray-100 rounded" />
              <div className="w-40 h-10 bg-gray-100 rounded" />
            </div>
          </div>
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <TableSkeleton rows={8} columns={8} />
          </div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="px-4 py-6 sm:px-0">
        <div className="flex justify-between items-center mb-6">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">
              Список заявок ({filteredRequests.length}
              {filteredRequests.length !== requests.length && (
                <span className="text-gray-500 text-base font-normal"> из {requests.length}</span>
              )}
              )
            </h2>
          </div>
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
                    <button onClick={() => { const a: Record<string,boolean>={}; ALL_COLS.forEach(c=>{a[c.key]=true;}); setVisibleCols(a); }}
                      className="text-xs text-blue-600 hover:text-blue-800">Показать все</button>
                  </div>
                </div>
              )}
            </div>
            <button
              onClick={() => downloadFile(requestsApi.exportPdf, 'requests.pdf', getExportParams())}
              className="bg-gray-100 text-gray-700 px-3 py-2 rounded hover:bg-gray-200 flex items-center shadow-sm text-sm"
              title="Экспорт в PDF"
            >
              📄 PDF
            </button>
            <button
              onClick={() => downloadFile(requestsApi.exportExcel, 'requests.xlsx', getExportParams())}
              className="bg-green-100 text-green-700 px-3 py-2 rounded hover:bg-green-200 flex items-center shadow-sm text-sm"
              title="Экспорт в Excel"
            >
              📊 Excel
            </button>
            {canCreate && (
              <button
                onClick={handleCreate}
                className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 flex items-center shadow-sm"
              >
                <span className="mr-2">+</span> Новая заявка
              </button>
            )}
          </div>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-6">
            {error}
          </div>
        )}

        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-4">
          <div className="flex flex-wrap gap-3 items-center">
            <div className="flex-1 min-w-[200px]">
              <input
                type="text"
                placeholder="🔍 Поиск по адресу, типу работ, номеру, клиенту..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
              />
            </div>
            <div>
              <select
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
              >
                <option value="all">Все статусы ({statusCounts.all})</option>
                {Object.entries(STATUS_LABELS).map(([key, { label }]) => (
                  <option key={key} value={key}>
                    {label} ({statusCounts[key] || 0})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <select
                value={filterPriority}
                onChange={(e) => setFilterPriority(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
              >
                <option value="all">Все приоритеты</option>
                {Object.entries(PRIORITY_LABELS).map(([key, { label }]) => (
                  <option key={key} value={key}>{label}</option>
                ))}
              </select>
            </div>
            <div>
              <select value={filterCategory} onChange={(e) => setFilterCategory(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none">
                <option value="all">Все категории</option>
                {categories.map(cat => (<option key={cat.id} value={cat.id}>{cat.name}</option>))}
              </select>
            </div>
            <div>
              <select value={filterVehicleId} onChange={(e) => setFilterVehicleId(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none">
                <option value="all">Вся техника</option>
                {vehicles.map(v => (<option key={v.id} value={v.id}>{v.name}</option>))}
              </select>
            </div>
            <div className="flex items-center gap-1">
              <input type="date" value={filterDateFrom} onChange={(e) => setFilterDateFrom(e.target.value)}
                className="px-2 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500 outline-none" title="Дата от" />
              <span className="text-gray-400">—</span>
              <input type="date" value={filterDateTo} onChange={(e) => setFilterDateTo(e.target.value)}
                className="px-2 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500 outline-none" title="Дата до" />
            </div>
            <div>
              <select value={sortBy + '_' + sortOrder}
                onChange={(e) => { const [f, o] = e.target.value.split('_'); setSortBy(f); setSortOrder(o as 'asc'|'desc'); }}
                className="px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none">
                <option value="created_at_desc">Сначала новые</option>
                <option value="created_at_asc">Сначала старые</option>
                <option value="planned_start_asc">По дате начала ↑</option>
                <option value="planned_start_desc">По дате начала ↓</option>
                <option value="priority_desc">По приоритету ↓</option>
              </select>
            </div>
            {(filterStatus !== 'all' || filterPriority !== 'all' || searchQuery || filterCategory !== 'all' || filterVehicleId !== 'all' || filterDateFrom || filterDateTo) && (
              <button
                onClick={() => { setFilterStatus('all'); setFilterPriority('all'); setSearchQuery(''); setFilterCategory('all'); setFilterVehicleId('all'); setFilterDateFrom(''); setFilterDateTo(''); setSortBy('created_at'); setSortOrder('desc'); }}
                className="px-3 py-2 text-sm text-gray-600 hover:text-gray-900"
              >
                ✕ Сбросить
              </button>
            )}
          </div>
        </div>

        <div className="bg-white shadow rounded-lg overflow-hidden">
          {filteredRequests.length === 0 ? (
            <div className="p-12 text-center text-gray-500">
              <div className="text-5xl mb-4">📋</div>
              <p className="text-lg">
                {requests.length === 0 ? 'Заявок пока нет' : 'Нет заявок по выбранным фильтрам'}
              </p>
              {canCreate && requests.length === 0 && (
                <p className="mt-2">Создайте первую заявку, нажав кнопку выше</p>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto overflow-y-auto max-h-[70vh] border border-gray-200 rounded">
            <table className="min-w-[1200px] w-full divide-y divide-gray-200">
              <thead className="bg-gray-50 sticky top-0 z-10 shadow-sm">
                <tr>
                  {isVis("id") && (<th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase whitespace-nowrap relative group select-none" style={colSt("id", 60)}>№<div className="absolute right-0 top-0 bottom-0 w-[3px] cursor-col-resize bg-gray-200 hover:bg-blue-500 transition-colors" onMouseDown={(e) => onMouseDownResize(e, "id", 60)} /></th>)}
                  {isVis("work_type") && (<th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase whitespace-nowrap relative group select-none" style={colSt("work_type", 150)}>Тип работы<div className="absolute right-0 top-0 bottom-0 w-[3px] cursor-col-resize bg-gray-200 hover:bg-blue-500 transition-colors" onMouseDown={(e) => onMouseDownResize(e, "work_type", 150)} /></th>)}
                  {isVis("address") && (<th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase whitespace-nowrap relative group select-none" style={colSt("address", 200)}>Адрес<div className="absolute right-0 top-0 bottom-0 w-[3px] cursor-col-resize bg-gray-200 hover:bg-blue-500 transition-colors" onMouseDown={(e) => onMouseDownResize(e, "address", 200)} /></th>)}
                  {isVis("period") && (<th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase whitespace-nowrap relative group select-none" style={colSt("period", 220)}>Период<div className="absolute right-0 top-0 bottom-0 w-[3px] cursor-col-resize bg-gray-200 hover:bg-blue-500 transition-colors" onMouseDown={(e) => onMouseDownResize(e, "period", 220)} /></th>)}
                  {isVis("category") && (<th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase whitespace-nowrap relative group select-none" style={colSt("category", 160)}>Категория<div className="absolute right-0 top-0 bottom-0 w-[3px] cursor-col-resize bg-gray-200 hover:bg-blue-500 transition-colors" onMouseDown={(e) => onMouseDownResize(e, "category", 160)} /></th>)}
                  {isVis("vehicle") && (<th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase whitespace-nowrap relative group select-none" style={colSt("vehicle", 160)}>Техника<div className="absolute right-0 top-0 bottom-0 w-[3px] cursor-col-resize bg-gray-200 hover:bg-blue-500 transition-colors" onMouseDown={(e) => onMouseDownResize(e, "vehicle", 160)} /></th>)}
                  {isVis("client") && (<th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase whitespace-nowrap relative group select-none" style={colSt("client", 160)}>Клиент<div className="absolute right-0 top-0 bottom-0 w-[3px] cursor-col-resize bg-gray-200 hover:bg-blue-500 transition-colors" onMouseDown={(e) => onMouseDownResize(e, "client", 160)} /></th>)}
                  {isVis("status") && (<th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase whitespace-nowrap relative group select-none" style={colSt("status", 120)}>Статус<div className="absolute right-0 top-0 bottom-0 w-[3px] cursor-col-resize bg-gray-200 hover:bg-blue-500 transition-colors" onMouseDown={(e) => onMouseDownResize(e, "status", 120)} /></th>)}
                  {isVis("priority") && (<th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase whitespace-nowrap relative group select-none" style={colSt("priority", 100)}>Приоритет<div className="absolute right-0 top-0 bottom-0 w-[3px] cursor-col-resize bg-gray-200 hover:bg-blue-500 transition-colors" onMouseDown={(e) => onMouseDownResize(e, "priority", 100)} /></th>)}
                  {isVis("amount") && (<th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase whitespace-nowrap relative group select-none" style={colSt("amount", 100)}>Сумма<div className="absolute right-0 top-0 bottom-0 w-[3px] cursor-col-resize bg-gray-200 hover:bg-blue-500 transition-colors" onMouseDown={(e) => onMouseDownResize(e, "amount", 100)} /></th>)}
                  {(canEdit || canDelete) && (
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase sticky right-0 bg-gray-50 shadow-[-2px_0_4px_-2px_rgba(0,0,0,0.1)]" style={{minWidth:"80px"}}>Действия</th>
                  )}
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {filteredRequests.map((req) => (
                  <tr
                    key={req.id}
                    onClick={() => handleRowClick(req)}
                    className="hover:bg-blue-50 cursor-pointer transition-colors"
                  >
                    {isVis("id") && (
                    <td className="px-4 py-4 whitespace-nowrap text-sm font-mono text-blue-600 font-medium">
                      #{req.id}
                    </td>
                    )}
                    {isVis("work_type") && (
                    <td className="px-4 py-4 text-sm text-gray-900">
                      <div className="font-medium">{req.work_type || '—'}</div>
                      <div className="text-xs text-gray-500">{req.request_type}</div>
                    </td>
                    )}
                    {isVis("address") && (
                    <td className="px-4 py-4 text-sm text-gray-600 max-w-xs truncate">
                      {req.object_address || '—'}
                    </td>
                    )}
                    {isVis("period") && (<td className="px-4 py-4 whitespace-nowrap text-xs text-gray-600">
                      <div>{formatDate(req.planned_start)} <span className="text-blue-500 text-[10px]">{req.planned_start ? new Date(req.planned_start).toLocaleTimeString('ru-RU',{hour:'2-digit',minute:'2-digit'}) : ''}</span></div>
                      <div className="text-gray-400">— {formatDate(req.planned_end)} <span className="text-blue-500 text-[10px]">{req.planned_end ? new Date(req.planned_end).toLocaleTimeString('ru-RU',{hour:'2-digit',minute:'2-digit'}) : ''}</span></div>
                    </td>)}
                    {isVis("category") && (<td className="px-4 py-4 whitespace-nowrap text-sm text-gray-600">
                      {req.vehicle_category_name || <span className="text-gray-400">—</span>}
                    </td>)}
                    {isVis("vehicle") && (<td className="px-4 py-4 whitespace-nowrap text-sm text-gray-700">
                      {(req as any).assigned_vehicle_name || <span className="text-gray-400">—</span>}
                    </td>)}
                    {isVis("client") && (
                    <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-700">
                      {req.client_name || <span className="text-gray-400">—</span>}
                    </td>
                    )}
                    {isVis("status") && (
                    <td className="px-4 py-4 whitespace-nowrap">
                      <span className={`px-2 py-1 text-xs font-semibold rounded-full ${STATUS_LABELS[req.status]?.color || 'bg-gray-100'}`}>
                        {STATUS_LABELS[req.status]?.label || req.status}
                      </span>
                    </td>
                    )}
                    {isVis("priority") && (
                    <td className="px-4 py-4 whitespace-nowrap text-sm">
                      <span className={PRIORITY_LABELS[req.priority]?.color || 'text-gray-600'}>
                        {PRIORITY_LABELS[req.priority]?.label || req.priority}
                      </span>
                    </td>
                    )}
                    {isVis("amount") && (
                    <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900 font-medium">
                      {formatMoney(req.estimated_amount)}
                    </td>
                    )}
                    {(canEdit || canDelete) && (
                      <td className="px-4 py-4 whitespace-nowrap text-right text-sm font-medium space-x-2 sticky right-0 bg-white shadow-[-2px_0_4px_-2px_rgba(0,0,0,0.1)]" onClick={(e) => e.stopPropagation()}>
                        {canEdit && (
                          <button
                            onClick={(e) => handleEdit(e, req)}
                            className="text-blue-600 hover:text-blue-900"
                          >
                            ✏️
                          </button>
                        )}
                        {canDelete && (
                          <button
                            onClick={(e) => handleDelete(e, req)}
                            className="text-red-600 hover:text-red-900"
                          >
                            🗑️
                          </button>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          )}
        </div>
      </div>

      {isModalOpen && (
        <RequestFormModal
          request={editingRequest}
          onClose={() => {
            setIsModalOpen(false);
            setEditingRequest(null);
          }}
          onSave={handleSave}
        />
      )}

      {deleteTarget && (
        <DeleteConfirmDialog
          title="Удалить заявку?"
          message={`Заявка #${deleteTarget.id} будет удалена безвозвратно.`}
          onConfirm={confirmDelete}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </Layout>
  );
};

export default RequestsPage;
