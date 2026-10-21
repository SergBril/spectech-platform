import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { reconciliationApi, type Reconciliation } from '../api/reconciliation';
import { financeApi } from '../api/finance';
import { downloadBlob } from '../api/export';
import { showToast } from '../utils/toast';
import { TableSkeleton, MetricCardSkeleton } from '../components/Skeleton';
import ReconciliationDetailModal from '../components/ReconciliationDetailModal';
import ReconciliationResolveModal from '../components/ReconciliationResolveModal';
import Layout from '../components/Layout';

const STATUS_LABELS: Record<string, { label: string; color: string; icon: string }> = {
  pending: { label: 'Ожидает', color: 'bg-gray-100 text-gray-800', icon: '⏳' },
  auto_approved: { label: 'Авто-подтверждено', color: 'bg-green-100 text-green-800', icon: '✅' },
  discrepancy_detected: { label: 'Расхождение', color: 'bg-yellow-100 text-yellow-800', icon: '⚠️' },
  manual_review: { label: 'Ручная проверка', color: 'bg-orange-100 text-orange-800', icon: '🔍' },
  resolved: { label: 'Разрешено', color: 'bg-blue-100 text-blue-800', icon: '✓' },
};

const formatDate = (dateStr: string) => {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleDateString('ru-RU');
};

const formatPercent = (value: number | null) => {
  if (value === null || value === undefined) return '—';
  return `${value.toFixed(2)}%`;
};

const formatNumber = (value: number | null, decimals: number = 2) => {
  if (value === null || value === undefined) return '—';
  return value.toLocaleString('ru-RU', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
};

export const ReconciliationPage: React.FC = () => {
  const { user, hasPermission } = useAuth();
  const navigate = useNavigate();

  const [reconciliations, setReconciliations] = useState<Reconciliation[]>([]);
  const [stats, setStats] = useState<{
    total: number;
    pending: number;
    auto_approved: number;
    manual_review: number;
    resolved: number;
  }>({ total: 0, pending: 0, auto_approved: 0, manual_review: 0, resolved: 0 });

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Фильтры
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [dateFrom, setDateFrom] = useState<string>('');
  const [dateTo, setDateTo] = useState<string>('');

  // Модальные окна
  const [selectedReconciliation, setSelectedReconciliation] = useState<Reconciliation | null>(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);
  const [isResolveModalOpen, setIsResolveModalOpen] = useState(false);
  const [resolveTarget, setResolveTarget] = useState<Reconciliation | null>(null);

  const canView = hasPermission('finance', 'view');
  const canEdit = hasPermission('finance', 'update');

  useEffect(() => {
    if (!canView) return;
    loadData();
  }, [canView, statusFilter, dateFrom, dateTo]);

  const loadData = async () => {
    try {
      setLoading(true);

      const params: any = { limit: 100 };
      if (statusFilter) params.status = statusFilter;
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;

      const [reconciliationsData, statsData] = await Promise.allSettled([
        reconciliationApi.getReconciliations(params),
        reconciliationApi.getStats(dateFrom && dateTo ? { date_from: dateFrom, date_to: dateTo } : undefined),
      ]);

      if (reconciliationsData.status === 'fulfilled') {
        setReconciliations(reconciliationsData.value);
      } else {
        console.error('Failed to load reconciliations:', reconciliationsData.reason);
      }

      if (statsData.status === 'fulfilled') {
        setStats(statsData.value);
      } else {
        console.error('Failed to load stats:', statsData.reason);
      }

      setError('');
    } catch (err: any) {
      console.error('Failed to load data:', err);
      setError('Не удалось загрузить данные сверок');
    } finally {
      setLoading(false);
    }
  };

  const handleViewDetails = (reconciliation: Reconciliation) => {
    setSelectedReconciliation(reconciliation);
    setIsDetailModalOpen(true);
  };

  const handleResolve = (reconciliation: Reconciliation) => {
    setResolveTarget(reconciliation);
    setIsResolveModalOpen(true);
  };

  const handleDownloadPdf = async (reconciliation: Reconciliation) => {
    try {
      const blob = await reconciliationApi.downloadPdf(reconciliation.id);
      downloadBlob(blob, `reconciliation_${reconciliation.id}.pdf`);
      showToast.success('PDF скачан');
    } catch (err: any) {
      showToast.error('Ошибка скачивания: ' + (err?.response?.data?.detail || err.message));
    }
  };

  const handleGenerateInvoice = async (reconciliation: Reconciliation) => {
    if (!confirm(`Создать счёт из сверки #${reconciliation.id}?`)) return;

    try {
      const invoice = await reconciliationApi.generateInvoice({
        reconciliation_id: reconciliation.id,
        include_fuel_compensation: true,
      });
      showToast.success(`Счёт ${invoice.document_number} создан`);
      loadData();
    } catch (err: any) {
      showToast.error('Ошибка создания счёта: ' + (err?.response?.data?.detail || err.message));
    }
  };

  const handleResolveSuccess = () => {
    setIsResolveModalOpen(false);
    setResolveTarget(null);
    loadData();
  };

  const getMaxDiffPercent = (rec: Reconciliation): number => {
    const diffs = [
      rec.moto_hours_diff_percent || 0,
      rec.odometer_diff_percent || 0,
      rec.fuel_diff_percent || 0,
    ];
    return Math.max(...diffs);
  };

  const getDiffColor = (percent: number): string => {
    if (percent > 15) return 'text-red-600 font-bold';
    if (percent > 5) return 'text-yellow-600 font-semibold';
    return 'text-green-600';
  };

  if (!canView) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-white rounded-lg shadow p-8 max-w-md text-center">
          <div className="text-5xl mb-4">🔒</div>
          <h2 className="text-xl font-bold text-gray-900 mb-2">Доступ запрещён</h2>
          <button onClick={() => navigate('/')} className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
            На главную
          </button>
        </div>
      </div>
    );
  }

  return (
    <Layout>

     <div className="px-4 py-6 sm:px-0">
       {/* Заголовок */}
       <div className="flex justify-between items-center mb-6">
         <h2 className="text-2xl font-bold text-gray-900">📊 Сверки данных</h2>
         <button
           onClick={() => navigate('/finance')}
           className="bg-gray-600 text-white px-4 py-2 rounded hover:bg-gray-700"
         >
           ← К финансам
         </button>
       </div>

       {error && (
         <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-6">
           {error}
         </div>
       )}

       {/* Карточки статистики */}
       {loading ? (
         <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6 mb-8">
           {[1, 2, 3, 4, 5].map((i) => (
             <MetricCardSkeleton key={i} />
           ))}
         </div>
       ) : (
         <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6 mb-8">
           <div className="bg-white rounded-lg shadow p-6">
             <div className="flex items-center justify-between mb-2">
               <h3 className="text-sm font-medium text-gray-500">Всего</h3>
               <span className="text-2xl">📋</span>
             </div>
             <div className="text-3xl font-bold text-gray-900">{stats.total}</div>
           </div>

           <div className="bg-white rounded-lg shadow p-6">
             <div className="flex items-center justify-between mb-2">
               <h3 className="text-sm font-medium text-gray-500">Ожидают</h3>
               <span className="text-2xl">⏳</span>
             </div>
             <div className="text-3xl font-bold text-gray-600">{stats.pending}</div>
           </div>

           <div className="bg-white rounded-lg shadow p-6">
             <div className="flex items-center justify-between mb-2">
               <h3 className="text-sm font-medium text-gray-500">Авто</h3>
               <span className="text-2xl">✅</span>
             </div>
             <div className="text-3xl font-bold text-green-600">{stats.auto_approved}</div>
           </div>

           <div className="bg-white rounded-lg shadow p-6">
             <div className="flex items-center justify-between mb-2">
               <h3 className="text-sm font-medium text-gray-500">Ручная проверка</h3>
               <span className="text-2xl">🔍</span>
             </div>
             <div className="text-3xl font-bold text-orange-600">{stats.manual_review}</div>
           </div>

           <div className="bg-white rounded-lg shadow p-6">
             <div className="flex items-center justify-between mb-2">
               <h3 className="text-sm font-medium text-gray-500">Разрешено</h3>
               <span className="text-2xl">✓</span>
             </div>
             <div className="text-3xl font-bold text-blue-600">{stats.resolved}</div>
           </div>
         </div>
       )}

       {/* Фильтры */}
       <div className="bg-white rounded-lg shadow p-4 mb-6">
         <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
           <div>
             <label className="block text-sm font-medium text-gray-700 mb-1">Статус</label>
             <select
               value={statusFilter}
               onChange={(e) => setStatusFilter(e.target.value)}
               className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
             >
               <option value="">Все статусы</option>
               <option value="pending">Ожидает</option>
               <option value="auto_approved">Авто-подтверждено</option>
               <option value="discrepancy_detected">Расхождение</option>
               <option value="manual_review">Ручная проверка</option>
               <option value="resolved">Разрешено</option>
             </select>
           </div>

           <div>
             <label className="block text-sm font-medium text-gray-700 mb-1">Дата от</label>
             <input
               type="date"
               value={dateFrom}
               onChange={(e) => setDateFrom(e.target.value)}
               className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
             />
           </div>

           <div>
             <label className="block text-sm font-medium text-gray-700 mb-1">Дата до</label>
             <input
               type="date"
               value={dateTo}
               onChange={(e) => setDateTo(e.target.value)}
               className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
             />
           </div>

           <div className="flex items-end">
             <button
               onClick={() => {
                 setStatusFilter('');
                 setDateFrom('');
                 setDateTo('');
               }}
               className="w-full px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
             >
               Сбросить фильтры
             </button>
           </div>
         </div>
       </div>

       {/* Таблица сверок */}
       <div className="bg-white rounded-lg shadow overflow-hidden">
         {loading ? (
           <div className="p-6">
             <TableSkeleton rows={10} columns={8} />
           </div>
         ) : reconciliations.length === 0 ? (
           <div className="text-center py-12 text-gray-500">
             <div className="text-5xl mb-4">📋</div>
             <p>Сверок пока нет</p>
           </div>
         ) : (
           <div className="overflow-x-auto overflow-y-auto max-h-[70vh] border border-gray-200 rounded">
            <table className="min-w-full divide-y divide-gray-200">
               <thead className="bg-gray-50 sticky top-0 z-10 shadow-sm">
                 <tr>
                   <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
                   <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Смена</th>
                   <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Моточасы</th>
                   <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Пробег</th>
                   <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Топливо</th>
                   <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Макс. расхождение</th>
                   <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Статус</th>
                   <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Действия</th>
                 </tr>
               </thead>
               <tbody className="bg-white divide-y divide-gray-200">
                 {reconciliations.map((rec) => {
                   const maxDiff = getMaxDiffPercent(rec);
                   const statusInfo = STATUS_LABELS[rec.reconciliation_status] || STATUS_LABELS.pending;
                   const canResolve = rec.reconciliation_status === 'manual_review' && canEdit;
                   const canGenerateInvoice = ['auto_approved', 'resolved'].includes(rec.reconciliation_status) && canEdit;

                   return (
                     <tr key={rec.id} className="hover:bg-gray-50">
                       <td className="px-4 py-3 whitespace-nowrap">
                         <button
                           onClick={() => handleViewDetails(rec)}
                           className="text-sm font-mono text-blue-600 hover:text-blue-900 hover:underline"
                         >
                           #{rec.id}
                         </button>
                       </td>
                       <td className="px-4 py-3 whitespace-nowrap">
                         <button
                           onClick={() => navigate(`/shifts/${rec.shift_task_id}`)}
                           className="text-sm text-blue-600 hover:text-blue-900 hover:underline"
                         >
                           Смена #{rec.shift_task_id}
                         </button>
                       </td>
                       <td className="px-4 py-3 whitespace-nowrap text-sm">
                         <div className="flex flex-col">
                           <span className="text-gray-600">
                             {formatNumber(rec.operator_moto_hours)} / {formatNumber(rec.telematics_moto_hours)}
                           </span>
                           <span className={`text-xs ${getDiffColor(rec.moto_hours_diff_percent || 0)}`}>
                             {formatPercent(rec.moto_hours_diff_percent)}
                           </span>
                         </div>
                       </td>
                       <td className="px-4 py-3 whitespace-nowrap text-sm">
                         <div className="flex flex-col">
                           <span className="text-gray-600">
                             {formatNumber(rec.operator_odometer, 0)} / {formatNumber(rec.telematics_odometer, 0)}
                           </span>
                           <span className={`text-xs ${getDiffColor(rec.odometer_diff_percent || 0)}`}>
                             {formatPercent(rec.odometer_diff_percent)}
                           </span>
                         </div>
                       </td>
                       <td className="px-4 py-3 whitespace-nowrap text-sm">
                         <div className="flex flex-col">
                           <span className="text-gray-600">
                             {formatNumber(rec.operator_fuel_used)} / {formatNumber(rec.telematics_fuel_used)}
                           </span>
                           <span className={`text-xs ${getDiffColor(rec.fuel_diff_percent || 0)}`}>
                             {formatPercent(rec.fuel_diff_percent)}
                           </span>
                         </div>
                       </td>
                       <td className="px-4 py-3 whitespace-nowrap text-sm">
                         <span className={`font-semibold ${getDiffColor(maxDiff)}`}>
                           {formatPercent(maxDiff)}
                         </span>
                       </td>
                       <td className="px-4 py-3 whitespace-nowrap">
                         <span className={`px-2 py-1 text-xs font-semibold rounded-full ${statusInfo.color}`}>
                           {statusInfo.icon} {statusInfo.label}
                         </span>
                       </td>
                       <td className="px-4 py-3 whitespace-nowrap text-right text-sm space-x-2">
                         <button
                           onClick={() => handleViewDetails(rec)}
                           className="text-blue-600 hover:text-blue-900"
                           title="Просмотр деталей"
                         >
                           👁️
                         </button>
                         <button
                           onClick={() => handleDownloadPdf(rec)}
                           className="text-purple-600 hover:text-purple-900"
                           title="Скачать PDF"
                         >
                           📄
                         </button>
                         {canResolve && (
                           <button
                             onClick={() => handleResolve(rec)}
                             className="text-orange-600 hover:text-orange-900 font-semibold"
                             title="Разрешить конфликт"
                           >
                             ⚖️
                           </button>
                         )}
                         {canGenerateInvoice && (
                           <button
                             onClick={() => handleGenerateInvoice(rec)}
                             className="text-green-600 hover:text-green-900 font-semibold"
                             title="Создать счёт"
                           >
                             💰
                           </button>
                         )}
                       </td>
                     </tr>
                   );
                 })}
               </tbody>
             </table>
           </div>
         )}
       </div>
     </div>
   </Layout>
  );
};

export default ReconciliationPage;
