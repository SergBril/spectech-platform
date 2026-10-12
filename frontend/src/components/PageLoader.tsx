import React from 'react';

export const PageLoader: React.FC = () => (
  <div className="min-h-[60vh] flex flex-col items-center justify-center">
    <div className="relative">
      <div className="w-12 h-12 border-4 border-blue-200 rounded-full animate-spin border-t-blue-600" />
    </div>
    <p className="mt-4 text-sm text-gray-500 animate-pulse">Загрузка...</p>
  </div>
);

export default PageLoader;