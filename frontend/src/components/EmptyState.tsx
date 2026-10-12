import React from 'react';

interface EmptyStateProps {
  icon: string;
  title: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
  secondaryActionLabel?: string;
  onSecondaryAction?: () => void;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon,
  title,
  description,
  actionLabel,
  onAction,
  secondaryActionLabel,
  onSecondaryAction,
}) => {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
      {/* Иконка с анимацией */}
      <div className="relative mb-6">
        <div className="text-7xl opacity-80 animate-bounce-slow">{icon}</div>
        {/* Декоративный круг */}
        <div className="absolute inset-0 bg-blue-50 rounded-full -z-10 scale-150 opacity-50" />
      </div>

      {/* Заголовок */}
      <h3 className="text-xl font-semibold text-gray-900 mb-2">{title}</h3>

      {/* Описание */}
      {description && (
        <p className="text-sm text-gray-500 max-w-md mb-6 leading-relaxed">
          {description}
        </p>
      )}

      {/* Кнопки действий */}
      {(actionLabel || secondaryActionLabel) && (
        <div className="flex flex-col sm:flex-row gap-3">
          {actionLabel && onAction && (
            <button
              onClick={onAction}
              className="px-5 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium shadow-sm hover:shadow-md"
            >
              {actionLabel}
            </button>
          )}
          {secondaryActionLabel && onSecondaryAction && (
            <button
              onClick={onSecondaryAction}
              className="px-5 py-2.5 bg-white text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors text-sm font-medium"
            >
              {secondaryActionLabel}
            </button>
          )}
        </div>
      )}
    </div>
  );
};

export default EmptyState;