import React, { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import apiClient from '../api/client';

const DocumentArchivePage: React.FC = () => {
  const [docs, setDocs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ q: '', doc_type: '' });
  const [pagination, setPagination] = useState({ page: 1, pages: 1, total: 0 });
  const [showUpload, setShowUpload] = useState(false);
  const [uploadForm, setUploadForm] = useState({ title: '', doc_type: 'report', doc_number: '', content_text: '' });
  const [uploadFile, setUploadFile] = useState<File | null>(null);

  const loadDocs = async (page = 1) => {
    try {
      setLoading(true);
      const params: any = { page, per_page: 20 };
      if (filters.q) params.q = filters.q;
      if (filters.doc_type) params.doc_type = filters.doc_type;
      const res = await apiClient.get('/shifts/documents/archive', { params });
      setDocs(Array.isArray(res.data.items) ? res.data.items : []);
      setPagination({ page: res.data.page, pages: res.data.pages, total: res.data.total });
    } catch {} finally { setLoading(false); }
  };

  useEffect(() => { loadDocs(); }, [filters]);

  const uploadDoc = async () => {
    if (!uploadForm.title) { alert('Укажите название документа'); return; }
    try {
      const formData = new FormData();
      formData.append('title', uploadForm.title);
      formData.append('doc_type', uploadForm.doc_type);
      formData.append('doc_number', uploadForm.doc_number);
      formData.append('content_text', uploadForm.content_text);
      if (uploadFile) formData.append('file', uploadFile);
      await apiClient.post('/shifts/documents/archive', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
      alert('✅ Документ добавлен');
      setShowUpload(false);
      setUploadForm({ title: '', doc_type: 'report', doc_number: '', content_text: '' });
      setUploadFile(null);
      loadDocs();
    } catch (err: any) { alert('Ошибка: ' + (err.response?.data?.detail || '')); }
  };

  const indexActs = async () => {
    if (!confirm('Индексировать все акты в архив?')) return;
    try {
      const res = await apiClient.post('/shifts/documents/archive/auto-index-acts');
      alert(`✅ ${res.data.message}`);
      loadDocs();
    } catch (err: any) { alert('Ошибка: ' + (err.response?.data?.detail || '')); }
  };

  const typeLabels: Record<string, string> = { act: '📄 Акт', invoice: '🧾 Счёт', contract: '📋 Договор', report: '📊 Отчёт' };
  const typeColors: Record<string, string> = { act: 'bg-blue-100 text-blue-700', invoice: 'bg-green-100 text-green-700', contract: 'bg-purple-100 text-purple-700', report: 'bg-orange-100 text-orange-700' };

  return (
    <Layout>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <h1 className="text-2xl font-bold text-gray-900">🗄️ Архив документов</h1>
          <div className="flex gap-2">
            <button onClick={indexActs} className="px-3 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200">🔄 Индексировать акты</button>
            <button onClick={() => setShowUpload(!showUpload)} className="px-3 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700">
              {showUpload ? '✕ Закрыть' : '📎 Загрузить документ'}
            </button>
          </div>
        </div>

        {/* Upload Form */}
        {showUpload && (
          <div className="bg-white rounded-xl shadow-sm border p-5 space-y-3">
            <h2 className="text-sm font-semibold text-gray-500 uppercase">Загрузка документа</h2>
            <div className="grid grid-cols-2 gap-3">
              <label className="block"><span className="text-xs text-gray-500">Название *</span>
                <input value={uploadForm.title} onChange={e => setUploadForm({...uploadForm, title: e.target.value})}
                  className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" /></label>
              <label className="block"><span className="text-xs text-gray-500">Тип</span>
                <select value={uploadForm.doc_type} onChange={e => setUploadForm({...uploadForm, doc_type: e.target.value})}
                  className="w-full mt-1 px-3 py-2 border rounded-lg text-sm">
                  <option value="report">Отчёт</option><option value="act">Акт</option>
                  <option value="invoice">Счёт</option><option value="contract">Договор</option>
                </select></label>
              <label className="block"><span className="text-xs text-gray-500">Номер</span>
                <input value={uploadForm.doc_number} onChange={e => setUploadForm({...uploadForm, doc_number: e.target.value})}
                  className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" /></label>
              <label className="block"><span className="text-xs text-gray-500">Файл</span>
                <input type="file" onChange={e => setUploadFile(e.target.files?.[0] || null)}
                  className="w-full mt-1 text-sm" /></label>
            </div>
            <label className="block"><span className="text-xs text-gray-500">Текст для поиска</span>
              <textarea value={uploadForm.content_text} onChange={e => setUploadForm({...uploadForm, content_text: e.target.value})}
                className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" rows={2} /></label>
            <button onClick={uploadDoc} className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium">💾 Сохранить</button>
          </div>
        )}

        {/* Search & Filter */}
        <div className="bg-white rounded-xl shadow-sm border p-4 flex gap-3 flex-wrap items-end">
          <label className="block flex-1 min-w-[250px]"><span className="text-xs text-gray-500">🔍 Поиск</span>
            <input placeholder="Поиск по названию, номеру, содержимому..." value={filters.q} onChange={e => setFilters({...filters, q: e.target.value})}
              className="mt-1 px-3 py-1.5 border rounded-lg text-sm w-full" /></label>
          <label className="block"><span className="text-xs text-gray-500">Тип</span>
            <select value={filters.doc_type} onChange={e => setFilters({...filters, doc_type: e.target.value})}
              className="mt-1 px-3 py-1.5 border rounded-lg text-sm w-36">
              <option value="">Все</option>
              <option value="act">Акт</option><option value="invoice">Счёт</option>
              <option value="contract">Договор</option><option value="report">Отчёт</option>
            </select></label>
          <button onClick={() => setFilters({ q: '', doc_type: '' })} className="px-3 py-1.5 text-gray-500 hover:text-gray-700 text-sm">✕ Сброс</button>
        </div>

        {/* Results */}
        <div className="flex justify-between items-center text-sm text-gray-500">
          <span>Найдено: {pagination.total} документов</span>
          <div className="flex gap-2">
            <button disabled={pagination.page <= 1} onClick={() => loadDocs(pagination.page - 1)} className="px-3 py-1 border rounded disabled:opacity-30">← Назад</button>
            <span className="py-1">{pagination.page} / {pagination.pages}</span>
            <button disabled={pagination.page >= pagination.pages} onClick={() => loadDocs(pagination.page + 1)} className="px-3 py-1 border rounded disabled:opacity-30">Вперёд →</button>
          </div>
        </div>

        {loading ? (
          <div className="flex justify-center py-12"><div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600"></div></div>
        ) : docs.length === 0 ? (
          <p className="text-gray-400 text-center py-8">Документы не найдены</p>
        ) : (
          <div className="space-y-2">
            {docs.map((d: any) => (
              <div key={d.id} className="bg-white rounded-xl shadow-sm border p-4 flex items-center justify-between hover:bg-gray-50 transition-colors">
                <div className="flex items-center gap-3">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${typeColors[d.doc_type] || 'bg-gray-100 text-gray-600'}`}>
                    {typeLabels[d.doc_type] || d.doc_type}
                  </span>
                  <div>
                    <p className="font-medium text-gray-900">{d.title}</p>
                    <p className="text-xs text-gray-500">{d.doc_number && `#${d.doc_number} • `}{d.created_at ? new Date(d.created_at).toLocaleDateString('ru-RU') : ''}</p>
                  </div>
                </div>
                {d.file_path && <span className="text-xs text-blue-600">📎 Файл</span>}
              </div>
            ))}
          </div>
        )}
      </div>
    </Layout>
  );
};

export default DocumentArchivePage;
