import React from 'react';

interface SkeletonProps {
  className?: string;
  count?: number;
  width?: string | number;
  height?: string | number;
  circle?: boolean;
}

export const Skeleton: React.FC<SkeletonProps> = ({
  className = '',
  count = 1,
  width,
  height,
  circle = false,
}) => {
  const style: React.CSSProperties = {
    width: width,
    height: height,
    borderRadius: circle ? '50%' : '6px',
  };

  const skeletons = [];
  for (let i = 0; i < count; i++) {
    skeletons.push(
      <div
        key={i}
        className={`skeleton ${className}`}
        style={style}
      />
    );
  }

  return <>{skeletons}</>;
};

// Карточка метрики для Dashboard
export const MetricCardSkeleton: React.FC = () => (
  <div className="bg-white rounded-lg shadow p-6 animate-pulse">
    <div className="flex items-center justify-between mb-4">
      <Skeleton width="60%" height={16} />
      <div className="w-10 h-10 rounded-lg skeleton" />
    </div>
    <Skeleton width="80%" height={32} className="mb-2" />
    <Skeleton width="40%" height={14} />
  </div>
);

// Карточка графика
export const ChartSkeleton: React.FC<{ height?: number }> = ({ height = 300 }) => (
  <div className="bg-white rounded-lg shadow p-6 animate-pulse">
    <Skeleton width="40%" height={24} className="mb-4" />
    <Skeleton width="100%" height={height} />
  </div>
);

// Строка таблицы
export const TableRowSkeleton: React.FC<{ columns?: number }> = ({ columns = 7 }) => (
  <tr className="animate-pulse">
    {Array.from({ length: columns }).map((_, i) => (
      <td key={i} className="px-4 py-3">
        <Skeleton width={i === 0 ? '60%' : '80%'} height={16} />
      </td>
    ))}
  </tr>
);

// Таблица целиком
export const TableSkeleton: React.FC<{ rows?: number; columns?: number }> = ({
  rows = 5,
  columns = 7,
}) => (
  <div className="overflow-x-auto">
    <table className="min-w-full divide-y divide-gray-200">
      <thead className="bg-gray-50">
        <tr>
          {Array.from({ length: columns }).map((_, i) => (
            <th key={i} className="px-4 py-3">
              <Skeleton width="70%" height={12} />
            </th>
          ))}
        </tr>
      </thead>
      <tbody className="bg-white divide-y divide-gray-200">
        {Array.from({ length: rows }).map((_, i) => (
          <TableRowSkeleton key={i} columns={columns} />
        ))}
      </tbody>
    </table>
  </div>
);

// Шапка заявки (RequestDetailPage)
export const RequestHeaderSkeleton: React.FC = () => (
  <div className="bg-white rounded-lg shadow p-6 animate-pulse">
    <div className="flex flex-col md:flex-row md:justify-between md:items-start gap-4 mb-6">
      <div className="flex items-center space-x-3">
        <div className="w-12 h-12 rounded-lg skeleton" />
        <div className="space-y-2">
          <Skeleton width={200} height={28} />
          <div className="flex space-x-2">
            <Skeleton width={80} height={24} />
            <Skeleton width={50} height={16} />
          </div>
        </div>
      </div>
      <Skeleton width={150} height={40} />
    </div>
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="bg-gray-50 p-3 rounded">
          <Skeleton width="40%" height={10} className="mb-2" />
          <Skeleton width="80%" height={16} />
        </div>
      ))}
    </div>
  </div>
);

// Timeline
export const TimelineSkeleton: React.FC = () => (
  <div className="bg-white rounded-lg shadow p-6 animate-pulse">
    <Skeleton width={200} height={24} className="mb-4" />
    <div className="relative">
      <div className="absolute left-6 top-0 bottom-0 w-0.5 bg-gray-200" />
      <div className="space-y-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="relative flex items-start gap-4 pl-14">
            <div className="absolute left-4 top-2 w-5 h-5 rounded-full bg-gray-300" />
            <div className="flex-1 bg-gray-50 rounded-lg p-4 space-y-2">
              <div className="flex justify-between">
                <Skeleton width={150} height={16} />
                <Skeleton width={100} height={12} />
              </div>
              <Skeleton width={200} height={14} />
            </div>
          </div>
        ))}
      </div>
    </div>
  </div>
);
