import React from 'react';
import type { Reconciliation } from '../api/reconciliation';

interface Props {
  reconciliation: Reconciliation;
  onClose: () => void;
}

const formatNumber = (value: number | null, decimals: number = 2) => {
  if (value === null || value === undefined) return '—';
  return value.toLocaleString('ru-RU', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
};

const formatPercent = (value: number | null) => {
  if (value === null || value === undefined) return '—';
  return `${value.toFixed(2)}%`;
};

const getDiffColor = (percent: number | null): string => {
  if (percent === null) return 'text-gray-600';
  if (percent > 15) return 'text-red-600 font-bold';
  if (percent > 5) return 'text-yellow-600 font-semibold';
  return 'text-green-600';
};

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  pending: { label: 'Ожидает', color: 'bg-gray-100 text-gray-800' },
  auto_approved: { label: 'Авто-подтверждено', color: 'bg-green-100 text-green-800' },
  discrepancy_detected: { label: 'Расхождение', color: 'bg-yellow-100 text-yellow-800' },
  manual_review: { label: 'Ручная проверка', color: 'bg-orange-100 text-orange-800' },
  resolved: { label: 'Разрешено', color: 'bg-blue-100 text-blue-800' },
};

export const ReconciliationDetailModal: React.FC<Props> = ({ reconciliation, onClose }) => {
  const statusInfo = STATUS_LABELS[reconciliation.reconciliation_status] || STATUS_LABELS.pending;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        {/* Заголовок */}
        <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex justify-between items-center">
          <h2 className="text-2xl font-bold text-gray-900">
            Сверка #{reconciliation.id}
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-2xl"
          >
            ×
          </button>
        </div>

        {/* Содержимое */}
        <div className="p-6 space-y-6">
          {/* Статус */}
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-gray-500">Статус:</span>
            <span className={`px-3 py-1 text-sm font-semibold rounded-full ${statusInfo.color}`}>
              {statusInfo.label}
            </span>
          </div>

          {/* Таблица сравнения */}
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-3">Сравнение данных</h3>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 border border-gray-300">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Показатель</th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Оператор</th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Телеметрия</th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Расхождение</th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Финал</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  <tr>
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">Моточасы</td>
                    <td className="px-4 py-3 text-sm text-center text-gray-600">
                      {formatNumber(reconciliation.operator_moto_hours)}
                    </td>
                    <td className="px-4 py-3 text-sm text-center text-gray-600">
                      {formatNumber(reconciliation.telematics_moto_hours)}
                    </td>
                    <td className={`px-4 py-3 text-sm text-center ${getDiffColor(reconciliation.moto_hours_diff_percent)}`}>
                      {formatPercent(reconciliation.moto_hours_diff_percent)}
                    </td>
                    <td className="px-4 py-3 text-sm text-center font-bold text-gray-900">
                      {formatNumber(reconciliation.final_moto_hours)}
                    </td>
                  </tr>
                  <tr className="bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">Пробег, км</td>
                    <td className="px-4 py-3 text-sm text-center text-gray-600">
                      {formatNumber(reconciliation.operator_odometer, 0)}
                    </td>
                    <td className="px-4 py-3 text-sm text-center text-gray-600">
                      {formatNumber(reconciliation.telematics_odometer, 0)}
                    </td>
                    <td className={`px-4 py-3 text-sm text-center ${getDiffColor(reconciliation.odometer_diff_percent)}`}>
                      {formatPercent(reconciliation.odometer_diff_percent)}
                    </td>
                    <td className="px-4 py-3 text-sm text-center font-bold text-gray-900">
                      {formatNumber(reconciliation.final_odometer, 0)}
                    </td>
                  </tr>
                  <tr>
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">Топливо, л</td>
                    <td className="px-4 py-3 text-sm text-center text-gray-600">
                      {formatNumber(reconciliation.operator_fuel_used)}
                    </td>
                    <td className="px-4 py-3 text-sm text-center text-gray-600">
                      {formatNumber(reconciliation.telematics_fuel_used)}
                    </td>
                    <td className={`px-4 py-3 text-sm text-center ${getDiffColor(reconciliation.fuel_diff_percent)}`}>
                      {formatPercent(reconciliation.fuel_diff_percent)}
                    </td>
                    <td className="px-4 py-3 text-sm text-center font-bold text-gray-900">
                      {formatNumber(reconciliation.final_fuel_used)}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Метаданные */}
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-3">Метаданные</h3>
            <div className="bg-gray-50 rounded-lg p-4 space-y-2">
              <div className="flex justify-between">
                <span className="text-sm font-medium text-gray-500">Смена:</span>
                <span className="text-sm text-gray-900">#{reconciliation.shift_task_id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm font-medium text-gray-500">Точек телеметрии:</span>
                <span className="text-sm text-gray-900">{reconciliation.telematics_data_points_count}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm font-medium text-gray-500">Источник решения:</span>
                <span className="text-sm text-gray-900">{reconciliation.decision_source || '—'}</span>
              </div>
              {reconciliation.decision_comment && (
                <div className="flex justify-between">
                  <span className="text-sm font-medium text-gray-500">Комментарий:</span>
                  <span className="text-sm text-gray-900">{reconciliation.decision_comment}</span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-sm font-medium text-gray-500">Создано:</span>
                <span className="text-sm text-gray-900">
                  {new Date(reconciliation.created_at).toLocaleString('ru-RU')}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Футер */}
        <div className="sticky bottom-0 bg-gray-50 border-t border-gray-200 px-6 py-4 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700"
          >
            Закрыть
          </button>
        </div>
      </div>
    </div>
  );
};

export default ReconciliationDetailModal;
