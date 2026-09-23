import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { CompanyProvider } from './contexts/CompanyContext';
import { WebSocketProvider } from './contexts/WebSocketContext';
import { Toaster } from 'react-hot-toast';
import { CompanySettingsPage } from './pages/CompanySettingsPage';
import { ContractorsPage } from './pages/ContractorsPage';

import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import RequestsPage from './pages/RequestsPage';
import DashboardPage from './pages/DashboardPage';
import VehiclesPage from './pages/VehiclesPage';
import MarketplacePage from './pages/MarketplacePage';  // ← ДОБАВИТЬ
import FinancePage from './pages/FinancePage';
import InvoicesPage from './pages/InvoicesPage';
import RequestDetailPage from './pages/RequestDetailPage';
import ActCreatePage from './pages/ActCreatePage';
import MaintenancePage from './pages/MaintenancePage';
import MaintenanceDetailPage from './pages/MaintenanceDetailPage';
import MaintenanceCreatePage from './pages/MaintenanceCreatePage';
import MaintenanceAnalyticsPage from './pages/MaintenanceAnalyticsPage';
import FuelAnalyticsPage from './pages/FuelAnalyticsPage';
import EmailTemplatesPage from './pages/EmailTemplatesPage';

import './index.css';

const ProtectedRoute = ({ children }: { children: JSX.Element }) => {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? children : <Navigate to="/login" replace />;
};

const GuestRoute = ({ children }: { children: JSX.Element }) => {
  const { isAuthenticated } = useAuth();
  return !isAuthenticated ? children : <Navigate to="/" replace />;
};

const AppRoutes = () => {
  return (
    <Routes>
      <Route path="/login" element={<GuestRoute><LoginPage /></GuestRoute>} />
      <Route path="/register" element={<GuestRoute><RegisterPage /></GuestRoute>} />
      <Route path="/" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
      <Route path="/vehicles" element={<ProtectedRoute><VehiclesPage /></ProtectedRoute>} />
      <Route path="/maintenance" element={<ProtectedRoute><MaintenancePage /></ProtectedRoute>} />
      <Route path="/maintenance/new" element={<ProtectedRoute><MaintenanceCreatePage /></ProtectedRoute>} />
      <Route path="/maintenance/:id" element={<ProtectedRoute><MaintenanceDetailPage /></ProtectedRoute>} />
      <Route path="/maintenance/analytics" element={<ProtectedRoute><MaintenanceAnalyticsPage /></ProtectedRoute>} />
      <Route path="/fuel/analytics" element={<ProtectedRoute><FuelAnalyticsPage /></ProtectedRoute>} />
      <Route path="/marketplace" element={<ProtectedRoute><MarketplacePage /></ProtectedRoute>} />  // ← ДОБАВИТЬ
      <Route path="/requests" element={<ProtectedRoute><RequestsPage /></ProtectedRoute>} />
      <Route path="/finance" element={<ProtectedRoute><FinancePage /></ProtectedRoute>} />
      <Route path="/invoices" element={<ProtectedRoute><InvoicesPage /></ProtectedRoute>} />
      <Route path="/email-templates" element={<ProtectedRoute><EmailTemplatesPage /></ProtectedRoute>} />
      <Route path="/requests/:id" element={<ProtectedRoute><RequestDetailPage /></ProtectedRoute>} />
      <Route path="/acts/new" element={<ProtectedRoute><ActCreatePage /></ProtectedRoute>} />
      <Route path="/settings/company" element={<ProtectedRoute><CompanySettingsPage /></ProtectedRoute>} />
      <Route path="/contractors" element={<ProtectedRoute><ContractorsPage /></ProtectedRoute>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 4000,
          style: {
            background: '#363636',
            color: '#fff',
            borderRadius: '8px',
          },
          success: {
            duration: 3000,
            iconTheme: {
              primary: '#10B981',
              secondary: '#fff',
            },
          },
          error: {
            duration: 5000,
            iconTheme: {
              primary: '#EF4444',
              secondary: '#fff',
            },
          },
        }}
      />
      <AuthProvider>
        <CompanyProvider>
          <WebSocketProvider>
            <AppRoutes />
          </WebSocketProvider>
        </CompanyProvider>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>
);
