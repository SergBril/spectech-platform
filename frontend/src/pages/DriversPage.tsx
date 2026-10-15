import React, { useEffect, useState, useRef } from 'react';
import { driversApi, type DriverProfile } from '../api/drivers';
import Layout from '../components/Layout';

const ALL_COLS = [
  { key: 'full_name', label: 'ФИО', def: 200 },
  { key: 'position', label: 'Должность', def: 150 },
  { key: 'license_number', label: 'ВУ №', def: 120 },
  { key: 'license_category', label: 'Категория', def: 80 },
  { key: 'license_expiry', label: 'ВУ до', def: 100 },
  { key: 'machinist_certificate', label: 'Корочки №', def: 120 },
  { key: 'machinist_type', label: 'Тип корочки', def: 140 },
  { key: 'machinist_expiry', label: 'Корочки до', def: 100 },
  { key: 'medical_expiry', label: 'Медосмотр до', def: 110 },
  { key: 'date_of_birth', label: 'Дата рожд.', def: 100 },
];

export const DriversPage: React.FC = () => {
  const [drivers, setDrivers] = useState<DriverProfile[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [editingDriver, setEditingDriver] = useState<DriverProfile | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);

  // Resizable + Visibility
  const [colWidths, setColWidths] = useState<Record<string, number>>({});
  const resizingRef = useRef<{ key: string; startX: number; startW: number } | null>(null);
  const [visibleCols, setVisibleCols] = useState<Record<string, boolean>>({});
  const [showColMenu, setShowColMenu] = useState(false);
  const colMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    try { const s = localStorage.getItem('drv_col_w'); if (s) setColWidths(JSON.parse(s)); } catch {}
    try { const v = localStorage.getItem('drv_vis_cols'); if (v) { setVisibleCols(JSON.parse(v)); return; } } catch {}
    const d: Record<string, boolean> = {};
    ALL_COLS.forEach(c => { d[c.key] = true; });
    setVisibleCols(d);
  }, []);

  useEffect(() => { try { localStorage.setItem('drv_col_w', JSON.stringify(colWidths)); } catch {} }, [colWidths]);
  useEffect(() => { if (Object.keys(visibleCols).length > 0) try { localStorage.setItem('drv_vis_cols', JSON.stringify(visibleCols)); } catch {} }, [visibleCols]);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!resizingRef.current) return;
      setColWidths(p => ({ ...p, [resizingRef.current!.key]: Math.max(50, resizingRef.current!.startW + e.clientX - resizingRef.current!.startX) }));
    };
    const onUp = () => { if (resizingRef.current) { resizingRef.current = null; document.body.style.cursor = ''; document.body.style.userSelect = ''; } };
    window.addEventListener('mousemove', onMove); window.addEventListener('mouseup', onUp);
    return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
  }, []);

  useEffect(() => {
    const h = (e: MouseEvent) => { if (colMenuRef.current && !colMenuRef.current.contains(e.target as Node)) setShowColMenu(false); };
    if (showColMenu) document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, [showColMenu]);

  const colSt = (k: string, d: number) => { const w = colWidths[k]; return w ? { width: w + 'px', minWidth: w + 'px' } : { minWidth: d + 'px' }; };
  const isVis = (k: string) => visibleCols[k] === undefined ? true : visibleCols[k] !== false;
  const toggleVis = (k: string) => setVisibleCols(p => ({ ...p, [k]: !isVis(k) }));
  const onResize = (e: React.MouseEvent, k: string, d: number) => { e.preventDefault(); e.stopPropagation(); resizingRef.current = { key: k, startX: e.clientX, startW: colWidths[k] || d }; document.body.style.cursor = 'col-resize'; document.body.style.userSelect = 'none'; };

  const loadDrivers = async () => {
    try {
      setLoading(true);
      const params: any = { limit: 200 }; if (search.trim()) params.search = search.trim(); const res = await driversApi.list(params);
      setDrivers(res.items);
      setTotal(res.total);
    } catch { /* ignore */ } finally { setLoading(false); }
  };

  useEffect(() => { loadDrivers(); }, [search]);

  const handleEdit = (driver: DriverProfile) => { setEditingDriver(driver); setShowForm(true); };
  const handleCloseForm = () => { setShowForm(false); setEditingDriver(null); loadDrivers(); };

  const fmtDate = (d: string | null) => d ? new Date(d).toLocaleDateString('ru-RU') : '—';

  const getExpiryColor = (d: string | null) => {
    if (!d) return 'text-gray-400';
    const diff = new Date(d).getTime() - Date.now();
    if (diff < 0) return 'text-red-600 font-semibold';
    if (diff < 30 * 24 * 3600 * 1000) return 'text-orange-600 font-semibold';
    return 'text-gray-600';
  };

  return (
    <Layout>
      <div className="px-4 py-6 sm:px-0">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-2xl font-bold text-gray-900">Водители ({total})</h2>
          <div className="flex gap-2">
            <button onClick={() => setShowCreateForm(true)} className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 flex items-center shadow-sm text-sm">
              <span className="mr-2">+</span> Добавить водителя
            </button>
            <div className="relative" ref={colMenuRef}>
              <button onClick={() => setShowColMenu(!showColMenu)} className="bg-gray-100 text-gray-700 px-3 py-2 rounded hover:bg-gray-200 flex items-center shadow-sm text-sm">⚙️ Столбцы</button>
              {showColMenu && (
                <div className="absolute right-0 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-xl z-50 py-2 min-w-[200px]">
                  <div className="px-3 py-1 text-xs font-semibold text-gray-500 uppercase">Видимость столбцов</div>
                  {ALL_COLS.map(col => (
                    <label key={col.key} className="flex items-center gap-2 px-3 py-1.5 hover:bg-gray-50 cursor-pointer text-sm">
                      <input type="checkbox" checked={isVis(col.key)} onChange={() => toggleVis(col.key)} className="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
                      {col.label}
                    </label>
                  ))}
                  <div className="border-t border-gray-100 mt-1 pt-1 px-3">
                    <button onClick={() => { const a: Record<string, boolean> = {}; ALL_COLS.forEach(c => { a[c.key] = true; }); setVisibleCols(a); }} className="text-xs text-blue-600 hover:text-blue-800">Показать все</button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-4">
          <input type="text" placeholder="🔍 Поиск по ФИО..." value={search} onChange={e => setSearch(e.target.value)}
            className="w-full max-w-md px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none" />
        </div>

        <div className="bg-white shadow rounded-lg overflow-hidden">
          {loading ? (
            <div className="p-12 text-center text-gray-500">Загрузка...</div>
          ) : drivers.length === 0 ? (
            <div className="p-12 text-center text-gray-500">Водители не найдены</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-[1400px] w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    {ALL_COLS.map(col => isVis(col.key) && (
                      <th key={col.key} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase whitespace-nowrap relative group select-none" style={colSt(col.key, col.def)}>
                        {col.label}
                        <div className="absolute right-0 top-0 bottom-0 w-[3px] cursor-col-resize bg-gray-200 hover:bg-blue-500 transition-colors" onMouseDown={e => onResize(e, col.key, col.def)} />
                      </th>
                    ))}
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase" style={{ minWidth: '80px' }}>Действия</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {drivers.map(drv => (
                    <tr key={drv.contractor_id} className="hover:bg-blue-50 transition-colors">
                      {isVis('full_name') && <td className="px-4 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{drv.full_name}</td>}
                      {isVis('position') && <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-600">{drv.position || '—'}</td>}
                      {isVis('license_number') && <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-600">{drv.license_number || '—'}</td>}
                      {isVis('license_category') && <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-600">{drv.license_category || '—'}</td>}
                      {isVis('license_expiry') && <td className={`px-4 py-4 whitespace-nowrap text-sm ${getExpiryColor(drv.license_expiry_date)}`}>{fmtDate(drv.license_expiry_date)}</td>}
                      {isVis('machinist_certificate') && <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-600">{drv.machinist_certificate || '—'}</td>}
                      {isVis('machinist_type') && <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-600">{drv.machinist_certificate_type || '—'}</td>}
                      {isVis('machinist_expiry') && <td className={`px-4 py-4 whitespace-nowrap text-sm ${getExpiryColor(drv.machinist_certificate_expiry)}`}>{fmtDate(drv.machinist_certificate_expiry)}</td>}
                      {isVis('medical_expiry') && <td className={`px-4 py-4 whitespace-nowrap text-sm ${getExpiryColor(drv.medical_cert_expiry)}`}>{fmtDate(drv.medical_cert_expiry)}</td>}
                      {isVis('date_of_birth') && <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-600">{fmtDate(drv.date_of_birth)}</td>}
                      <td className="px-4 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <button onClick={() => handleEdit(drv)} className="text-blue-600 hover:text-blue-900">✏️</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Modal Form */}
      {showForm && editingDriver && (
        <DriverFormModal driver={editingDriver} onClose={handleCloseForm} />
      )}

      {/* Create Driver Modal */}
      {showCreateForm && (
        <CreateDriverModal onClose={() => { setShowCreateForm(false); loadDrivers(); }} />
      )}
    </Layout>
  );
};

// === Inline Form Modal Component ===
const DriverFormModal: React.FC<{ driver: DriverProfile; onClose: () => void }> = ({ driver, onClose }) => {
  const [form, setForm] = useState<Record<string, any>>({
    date_of_birth: driver.date_of_birth || '',
    passport_series: driver.passport_series || '',
    passport_number: driver.passport_number || '',
    passport_issued_by: driver.passport_issued_by || '',
    passport_issue_date: driver.passport_issue_date || '',
    license_number: driver.license_number || '',
    license_category: driver.license_category || '',
    license_issue_date: driver.license_issue_date || '',
    license_expiry_date: driver.license_expiry_date || '',
    machinist_certificate: driver.machinist_certificate || '',
    machinist_certificate_type: driver.machinist_certificate_type || '',
    machinist_certificate_expiry: driver.machinist_certificate_expiry || '',
    medical_cert_expiry: driver.medical_cert_expiry || '',
    safety_training_expiry: driver.safety_training_expiry || '',
    notes: driver.notes || '',
  });
  const [saving, setSaving] = useState(false);

  const handleChange = (field: string, value: string) => setForm(p => ({ ...p, [field]: value }));

  const handleSave = async () => {
    setSaving(true);
    try {
      await driversApi.updateProfile(driver.contractor_id, form);
      onClose();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Ошибка сохранения');
    } finally { setSaving(false); }
  };

  const Field = ({ label, field, type = 'text' }: { label: string; field: string; type?: string }) => (
    <div>
      <label className="block text-xs font-medium text-gray-500 mb-1">{label}</label>
      <input type={type} value={form[field] || ''} onChange={e => handleChange(field, e.target.value)}
        className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
    </div>
  );

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-3xl max-h-[90vh] overflow-y-auto m-4">
        <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center sticky top-0 bg-white z-10">
          <h3 className="text-lg font-bold text-gray-900">Профиль: {driver.full_name}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">✕</button>
        </div>
        <div className="p-6 space-y-6">
          <div>
            <h4 className="text-sm font-semibold text-gray-700 mb-3 uppercase border-b pb-1">📋 Персональные данные</h4>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Дата рождения" field="date_of_birth" type="date" />
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Должность</label>
                <input type="text" value={driver.position || ''} disabled className="w-full px-3 py-2 border border-gray-200 rounded text-sm bg-gray-50 text-gray-500" />
              </div>
            </div>
          </div>
          <div>
            <h4 className="text-sm font-semibold text-gray-700 mb-3 uppercase border-b pb-1">🛂 Паспорт</h4>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Серия" field="passport_series" />
              <Field label="Номер" field="passport_number" />
              <div className="col-span-2"><Field label="Кем выдан" field="passport_issued_by" /></div>
              <Field label="Дата выдачи" field="passport_issue_date" type="date" />
            </div>
          </div>
          <div>
            <h4 className="text-sm font-semibold text-gray-700 mb-3 uppercase border-b pb-1">🚗 Водительское удостоверение</h4>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Номер ВУ" field="license_number" />
              <Field label="Категория" field="license_category" />
              <Field label="Дата выдачи" field="license_issue_date" type="date" />
              <Field label="Действительно до" field="license_expiry_date" type="date" />
            </div>
          </div>
          <div>
            <h4 className="text-sm font-semibold text-gray-700 mb-3 uppercase border-b pb-1">🏗️ Удостоверение машиниста</h4>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Номер корочки" field="machinist_certificate" />
              <Field label="Тип (экскаваторщик, крановщик...)" field="machinist_certificate_type" />
              <Field label="Действительно до" field="machinist_certificate_expiry" type="date" />
            </div>
          </div>
          <div>
            <h4 className="text-sm font-semibold text-gray-700 mb-3 uppercase border-b pb-1">🏥 Прочее</h4>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Медосмотр до" field="medical_cert_expiry" type="date" />
              <Field label="Охрана труда до" field="safety_training_expiry" type="date" />
              <div className="col-span-2">
                <label className="block text-xs font-medium text-gray-500 mb-1">Заметки</label>
                <textarea value={form.notes || ''} onChange={e => handleChange('notes', e.target.value)} rows={2}
                  className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
              </div>
            </div>
          </div>
        </div>
        <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3 sticky bottom-0 bg-white">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900">Отмена</button>
          <button onClick={handleSave} disabled={saving}
            className="px-6 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50">
            {saving ? 'Сохранение...' : 'Сохранить'}
          </button>
        </div>
      </div>
    </div>
  );
};


const CreateDriverModal: React.FC<{ onClose: () => void }> = ({ onClose }) => {
  const [form, setForm] = useState({
    full_name: '',
    position: 'Водитель',
    phone: '',
    email: '',
  });
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!form.full_name.trim()) { alert('ФИО обязательно'); return; }
    setSaving(true);
    try {
      await driversApi.create(form);
      onClose();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Ошибка создания');
    } finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md m-4">
        <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
          <h3 className="text-lg font-bold text-gray-900">Добавить водителя</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">✕</button>
        </div>
        <div className="p-6 space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">ФИО *</label>
            <input type="text" value={form.full_name} onChange={e => setForm(p => ({ ...p, full_name: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Должность</label>
            <input type="text" value={form.position} onChange={e => setForm(p => ({ ...p, position: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Телефон</label>
            <input type="text" value={form.phone} onChange={e => setForm(p => ({ ...p, phone: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Email</label>
            <input type="email" value={form.email} onChange={e => setForm(p => ({ ...p, email: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
          </div>
          <div className="text-xs text-gray-500">
            После создания вы сможете заполнить документы (ВУ, паспорт, корочки) в редакторе профиля.
          </div>
        </div>
        <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900">Отмена</button>
          <button onClick={handleSave} disabled={saving}
            className="px-6 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50">
            {saving ? 'Создание...' : 'Создать'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default DriversPage;