import React from 'react';
import { FuelAnomaly } from '../api/fuel';
import { AlertTriangle, AlertCircle, Info, X } from 'lucide-react';

interface Props {
  anomalies: FuelAnomaly[];
  onDismiss?: (index: number) => void;
}

const SEVERITY_CONFIG = {
  critical: {
    icon: AlertTriangle,
    bgColor: 'bg-red-50',
    borderColor: 'border-red-500',
    iconColor: 'text-red-600',
    textColor: 'text-red-800',
    label: 'Критично',
  },
  warning: {
    icon: AlertCircle,
    bgColor: 'bg-yellow-50',
    borderColor: 'border-yellow-500',
    iconColor: 'text-yellow-600',
    textColor: 'text-yellow-800',
    label: 'Внимание',
  },
  info: {
    icon: Info,
    bgColor: 'bg-blue-50',
    borderColor: 'border-blue-500',
    iconColor: 'text-blue-600',
    textColor: 'text-blue-800',
    label: 'Информация',
  },
};

const TYPE_LABELS = {
  drain: '🚨 Слив топлива',
  high_consumption: '📈 Перерасход',
  expensive_refuel: '💸 Дорогая заправка',
};

export const FuelAnomalyAlerts: React.FC<Props> = ({ anomalies, onDismiss }) => {
  if (anomalies.length === 0) return null;

  return (
    <div className="space-y-3 mb-6">
      {anomalies.map((anomaly, index) => {
        const config = SEVERITY_CONFIG[anomaly.severity];
        const Icon = config.icon;

        return (
          <div
            key={index}
            className={`${config.bgColor} border-l-4 ${config.borderColor} rounded-lg shadow-sm p-4`}
          >
            <div className="flex items-start">
              <div className="flex-shrink-0">
                <Icon className={`h-6 w-6 ${config.iconColor}`} />
              </div>
              <div className="ml-3 flex-1">
                <div className="flex items-center justify-between">
                  <h3 className={`text-sm font-bold ${config.textColor}`}>
                    {TYPE_LABELS[anomaly.type]} — {anomaly.vehicle_name}
                  </h3>
                  {onDismiss && (
                    <button
                      onClick={() => onDismiss(index)}
                      className="text-gray-400 hover:text-gray-600"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  )}
                </div>
                <p className={`text-sm mt-1 ${config.textColor}`}>
                  {anomaly.description}
                </p>
                {anomaly.occurred_at && (
                  <p className="text-xs text-gray-600 mt-1">
                    {new Date(anomaly.occurred_at).toLocaleString('ru-RU')}
                  </p>
                )}

                {/* Детали аномалии */}
                <div className="mt-2 text-xs text-gray-700 space-y-1">
                  {anomaly.type === 'drain' && (
                    <>
                      <div>
                        <span className="font-medium">Объём:</span> {anomaly.details.volume} л
                      </div>
                      {anomaly.details.fuel_level_before && (
                        <div>
                          <span className="font-medium">Уровень до:</span>{' '}
                          {anomaly.details.fuel_level_before} л →{' '}
                          <span className="font-medium">после:</span>{' '}
                          {anomaly.details.fuel_level_after} л
                        </div>
                      )}
                    </>
                  )}

                  {anomaly.type === 'high_consumption' && (
                    <>
                      <div>
                        <span className="font-medium">Фактический расход:</span>{' '}
                        {anomaly.details.actual_liters_per_hour} л/ч
                      </div>
                      <div>
                        <span className="font-medium">Нормативный расход:</span>{' '}
                        {anomaly.details.expected_liters_per_hour} л/ч
                      </div>
                      <div>
                        <span className="font-medium">Отклонение:</span>{' '}
                        +{anomaly.details.deviation_percent}%
                      </div>
                    </>
                  )}

                  {anomaly.type === 'expensive_refuel' && (
                    <>
                      <div>
                        <span className="font-medium">Цена:</span>{' '}
                        {anomaly.details.price_per_liter} ₽/л
                      </div>
                      <div>
                        <span className="font-medium">Средняя цена:</span>{' '}
                        {anomaly.details.avg_price} ₽/л
                      </div>
                      <div>
                        <span className="font-medium">Отклонение:</span>{' '}
                        +{anomaly.details.deviation_percent}%
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};
