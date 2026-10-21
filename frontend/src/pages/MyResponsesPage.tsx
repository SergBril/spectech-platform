import React, { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import apiClient from '../api/client';

interface ResponseItem {
  id: number;
  request_id: number;
  vehicle_id: number;
  vehicle_name: string;
  status: string;
  request_address: string | null;
  request_work_type: string | null;
  created_at: string | null;
}

const statusConfig: Record<string, { label: string; color: string }> = {
  pending_approval: { label: '⏳ На рассмотрении', color: 'bg-yellow-100 text-yellow-800' },
  approved: { label: '✅ Одобрено', color: 'bg-green-100 text-green-800' },
  rejected: { label: '❌ Отклонено', color: 'bg-red-100 text-red-800' },
};

const MyResponsesPage: React.FC = () => {
  const [responses, setResponses] = useState<ResponseItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { loadResponses(); }, []);

  const loadResponses = async () => {
    try {
      const res = await apiClient.get('/public/marketplace/my-responses');
      setResponses(Array.isArray(res.data) ? res.data : []);
    } catch (err) { console.error('Failed:', err); }
    finally { setLoading(false); }
  };

  return (
    <Layout>
      <div className="p-6 max-w-5xl mx-auto">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">✋ Мои отклики на заявки</h1>
        {loading ? (
          <div className="flex justify-center py-12"><div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600"></div></div>
        ) : responses.length === 0 ? (
          <div className="text-center py-12 bg-gray-50 rounded-lg">
            <p className="text-xl text-gray-500 mb-2">📭 Нет откликов</p>
            <p className="text-sm text-gray-400">Откликнитесь на заявки в маркетплейсе</p>
          </div>
        ) : (
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50"><tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Заявка</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Техника</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Адрес</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Статус</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Дата</th>
              </tr></thead>
              <tbody className="divide-y divide-gray-200">
                {responses.map((r) => {
                  const cfg = statusConfig[r.status] || { label: r.status, color: 'bg-gray-100 text-gray-800' };
                  return (<tr key={r.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium text-blue-600">#{r.request_id}</td>
                    <td className="px-4 py-3 text-sm text-gray-900">{r.vehicle_name}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">{r.request_address || '—'}</td>
                    <td className="px-4 py-3 text-sm"><span className={`px-2 py-1 rounded-full text-xs font-medium ${cfg.color}`}>{cfg.label}</span></td>
                    <td className="px-4 py-3 text-sm text-gray-500">{r.created_at ? new Date(r.created_at).toLocaleDateString('ru-RU') : '—'}</td>
                  </tr>);
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Layout>
  );
};
export default MyResponsesPage;
