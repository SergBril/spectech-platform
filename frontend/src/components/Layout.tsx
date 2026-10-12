import React from 'react';
import Sidebar from './Sidebar';
import NotificationBell from './NotificationBell';

interface LayoutProps {
  children: React.ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({ children }) => {
  return (
    <div className="min-h-screen bg-gray-50">
      <Sidebar />
      <div className="ml-64 transition-all duration-300">
        {/* Top bar */}
        <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6 sticky top-0 z-30">
          <div className="text-sm text-gray-500">
            СпецТехника Про • Управление парком
          </div>
          <NotificationBell />
        </header>
        
        {/* Main content - ЕДИНСТВЕННЫЙ <main> во всём приложении */}
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          {children}
        </main>
      </div>
    </div>
  );
};

export default Layout;