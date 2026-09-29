import React, { useState } from 'react';
import type { Reconciliation } from '../api/reconciliation';
import { reconciliationApi } from '../api/reconciliation';
import { showToast } from '../utils/toast';

interface Props {
  reconciliation: Reconciliation;
  onClose: () => void;
  onSuccess: () => void;
}

export const ReconciliationResolveModal: React.FC<Props> = ({ reconciliation, onClose, onSuccess }) => {
  const [decisionSource, setDecisionSource] = useState<'operator' | 'telematics' | 'average' | 'manual'>('telematics');
  const [finalMotoHours, setFinalMotoHours] = useState<number>(reconciliation.telematics_moto_hours || 0);
  const [finalOdometer, setFinalOdometer] = useState<number>(reconciliation.telematics_odometer || 0);
  const [finalFuelUsed, setFinalFuelUsed] = useState<number>(reconciliation.telematics_fuel_used || 0);
  const [comment, setComment] = useState('');
  const [loading, setLoading] = useState(false);

  const handleQuickSelect = (source: 'operator' | 'telematics' | 'average') => {
    setDecisionSource(source);

    if (source === 'operator') {
      setFinalMotoHours(reconciliation.operator_moto_hours || 0);
      setFinalOdometer(reconciliation.operator_odometer || 0);
      setFinalFuelUsed(reconciliation.operator_fuel_used || 0);
    } else if (source === 'telematics') {
      setFinalMotoHours(reconciliation.telematics_moto_hours || 0);
      setFinalOdometer(reconciliation.telematics_odometer || 0);
      setFinalFuelUsed(reconciliation.telematics_fuel_used || 0);
    } else if (source === 'average') {
      setFinalMotoHours(((reconciliation.operator_moto_hours || 0) + (reconciliation.telematics_moto_hours || 0)) / 2);
      setFinalOdometer(((reconciliation.operator_odometer || 0) + (reconciliation.telematics_odometer || 0)) / 2);
      setFinalFuelUsed(((reconciliation.operator_fuel_used || 0) + (reconciliation.telematics_fuel_used || 0)) / 2);
    }
  };

  const handleSubmit = async () => {
    try {
      setLoading(true);

      await reconciliationApi.resolveReconciliation(reconciliation.id, {
        decision_source: decisionSource,
        final_moto_hours: finalMotoHours,
        final_odometer: finalOdometer,
        final_fuel_used: finalFuelUsed,
        decision_comment: comment || undefined,
      });

      showToast.success('Сверка разрешена');
      onSuccess();
    } catch (err: any) {
      showToast.error('Ошибка: ' + (err?.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Заголовок */}
        <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex justify-between items-center">
          <h2 className="text-2xl font-bold text-gray-900">
            ⚖️ Разрешение конфликта (Сверка #{reconciliation.id})
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-2xl"
            disabled={loading}
          >
            ×
          </button>
        </div>

        {/* Содержимое */}
        <div className="p-6 space-y-6">
          {/* Быстрый выбор */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Источник решения
            </label>
            <div className="grid grid-cols-4 gap-2">
              <button
                onClick={() => handleQuickSelect('operator')}
                className={`px-4 py-2 rounded border-2 ${
                  decisionSource === 'operator'
                    ? 'border-blue-500 bg-blue-50 text-blue-700'
                    : 'border-gray-300 text-gray-700 hover:bg-gray-50'
                }`}
              >
                Оператор
              </button>
              <button
                onClick={() => handleQuickSelect('telematics')}
                className={`px-4 py-2 rounded border-2 ${
                  decisionSource === 'telematics'
                    ? 'border-blue-500 bg-blue-50 text-blue-700'
                    : 'border-gray-300 text-gray-700 hover:bg-gray-50'
                }`}
              >
                Телеметрия
              </button>
              <button
                onClick={() => handleQuickSelect('average')}
                className={`px-4 py-2 rounded border-2 ${
                  decisionSource === 'average'
                    ? 'border-blue-500 bg-blue-50 text-blue-700'
                    : 'border-gray-300 text-gray-700 hover:bg-gray-50'
                }`}
              >
                Среднее
              </button>
              <button
                onClick={() => setDecisionSource('manual')}
                className={`px-4 py-2 rounded border-2 ${
                  decisionSource === 'manual'
                    ? 'border-blue-500 bg-blue-50 text-blue-700'
                    : 'border-gray-300 text-gray-700 hover:bg-gray-50'
                }`}
              >
                Вручную
              </button>
            </div>
          </div>

          {/* Финальные значения */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-gray-900">Финальные значения</h3>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Моточасы
              </label>
              <input
                type="number"
                step="0.01"
                value={finalMotoHours}
                onChange={(e) => setFinalMotoHours(parseFloat(e.target.value) || 0)}
                disabled={decisionSource !== 'manual'}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
              />
              <div className="text-xs text-gray-500 mt-1">
                Оператор: {reconciliation.operator_moto_hours} | Телеметрия: {reconciliation.telematics_moto_hours}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Пробег (км)
              </label>
              <input
                type="number"
                step="1"
                value={finalOdometer}
                onChange={(e) => setFinalOdometer(parseFloat(e.target.value) || 0)}
                disabled={decisionSource !== 'manual'}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
              />
              <div className="text-xs text-gray-500 mt-1">
                Оператор: {reconciliation.operator_odometer} | Телеметрия: {reconciliation.telematics_odometer}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Топливо (л)
              </label>
              <input
                type="number"
                step="0.01"
                value={finalFuelUsed}
                onChange={(e) => setFinalFuelUsed(parseFloat(e.target.value) || 0)}
                disabled={decisionSource !== 'manual'}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
              />
              <div className="text-xs text-gray-500 mt-1">
                Оператор: {reconciliation.operator_fuel_used} | Телеметрия: {reconciliation.telematics_fuel_used}
              </div>
            </div>
          </div>

          {/* Комментарий */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Комментарий (опционально)
            </label>
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Причина решения..."
            />
          </div>
        </div>

        {/* Футер */}
        <div className="sticky bottom-0 bg-gray-50 border-t border-gray-200 px-6 py-4 flex justify-end gap-3">
          <button
            onClick={onClose}
            disabled={loading}
            className="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 disabled:opacity-50"
          >
            Отмена
          </button>
          <button
            onClick={handleSubmit}
            disabled={loading}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? 'Сохранение...' : 'Разрешить конфликт'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ReconciliationResolveModal;
