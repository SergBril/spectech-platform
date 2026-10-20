import './lib/sentry'; // Sentry must be imported FIRST

import React, { Suspense, lazy } from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { CompanyProvider } from './contexts/CompanyContext';
import { WebSocketProvider } from './contexts/WebSocketContext';
import { Toaster } from 'react-hot-toast';
import PageLoader from './components/PageLoader';
import { Sentry } from './lib/sentry';

// Lazy-loaded pages
import {
  DashboardPage,
  FinancePage,
  CompanyProfilePage,
  MarketplacePage,
  VehiclesPage,
  DriversPage,
  RequestsPage,
  ContractorsPage,
  ContractorDetailPage,
  MaintenancePage,
  MaintenanceDetailPage,
  MaintenanceCreatePage,
  MaintenanceAnalyticsPage,
  FuelAnalyticsPage,
  ReconciliationPage,
  InvoicesPage,
  EmailTemplatesPage,
  EmailLogsPage,
  CompanySettingsPage,
  MyListingsPage,
  RequestDetailPage,
  ActCreatePage,
  VehicleDetailPage,
} from './pages';

// ╨Ы╤С╨│╨║╨╕╨╡ ╤Б╤В╤А╨░╨╜╨╕╤Ж╤Л тАФ ╨╖╨░╨│╤А╤Г╨╢╨░╤О╤В╤Б╤П ╤Б╤А╨░╨╖╤Г
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';

import './index.css';

const ProtectedRoute = ({ children }: { children: JSX.Element }) => {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? children : <Navigate to="/login" replace />;
};

const GuestRoute = ({ children }: { children: JSX.Element }) => {
  const { isAuthenticated } = useAuth();
  return !isAuthenticated ? children : <Navigate to="/" replace />;
};

const BankStatementsPage = lazy(() => import('./pages/BankStatementsPage'));
const SalariesPage = lazy(() => import('./pages/SalariesPage'));
const MapPage = lazy(() => import('./pages/MapPage'));
const DriverLoginPage = lazy(() => import('./pages/driver/DriverLoginPage'));
const DriverDashboardPage = lazy(() => import('./pages/driver/DriverDashboardPage'));
const ShiftReportPage = lazy(() => import('./pages/driver/ShiftReportPage'));
const AdminDashboardPage = lazy(() => import('./pages/admin/AdminDashboardPage'));
const GpsAdminPage = lazy(() => import('./pages/admin/GpsAdminPage'));

const AppRoutes = () => {
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route path="/login" element={<GuestRoute><LoginPage /></GuestRoute>} />
        <Route path="/register" element={<GuestRoute><RegisterPage /></GuestRoute>} />
        <Route path="/" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
        <Route path="/vehicles" element={<ProtectedRoute><VehiclesPage /></ProtectedRoute>} />
        <Route path="/drivers" element={<ProtectedRoute><DriversPage /></ProtectedRoute>} />
        <Route path="/maintenance" element={<ProtectedRoute><MaintenancePage /></ProtectedRoute>} />
        <Route path="/maintenance/new" element={<ProtectedRoute><MaintenanceCreatePage /></ProtectedRoute>} />
        <Route path="/maintenance/:id" element={<ProtectedRoute><MaintenanceDetailPage /></ProtectedRoute>} />
        <Route path="/maintenance/analytics" element={<ProtectedRoute><MaintenanceAnalyticsPage /></ProtectedRoute>} />
        <Route path="/fuel/analytics" element={<ProtectedRoute><FuelAnalyticsPage /></ProtectedRoute>} />
        <Route path="/marketplace" element={<ProtectedRoute><MarketplacePage /></ProtectedRoute>} />
        <Route path="/requests" element={<ProtectedRoute><RequestsPage /></ProtectedRoute>} />
        <Route path="/finance" element={<ProtectedRoute><FinancePage /></ProtectedRoute>} />
        <Route path="/invoices" element={<ProtectedRoute><InvoicesPage /></ProtectedRoute>} />
        <Route path="/email-templates" element={<ProtectedRoute><EmailTemplatesPage /></ProtectedRoute>} />
        <Route path="/email-logs" element={<ProtectedRoute><EmailLogsPage /></ProtectedRoute>} />
        <Route path="/requests/:id" element={<ProtectedRoute><RequestDetailPage /></ProtectedRoute>} />
        <Route path="/acts/new" element={<ProtectedRoute><ActCreatePage /></ProtectedRoute>} />
        <Route path="/settings/company" element={<ProtectedRoute><CompanySettingsPage /></ProtectedRoute>} />
        <Route path="/contractors" element={<ProtectedRoute><ContractorsPage /></ProtectedRoute>} />
        <Route path="/contractors/:id" element={<ProtectedRoute><ContractorDetailPage /></ProtectedRoute>} />
        <Route path="/reconciliation" element={<ProtectedRoute><ReconciliationPage /></ProtectedRoute>} />
        <Route path="/marketplace/:id" element={<ProtectedRoute><VehicleDetailPage /></ProtectedRoute>} />
        <Route path="/companies/:id" element={<ProtectedRoute><CompanyProfilePage /></ProtectedRoute>} />
        <Route path="/my-listings" element={<ProtectedRoute><MyListingsPage /></ProtectedRoute>} />
        <Route path="/salaries" element={<ProtectedRoute><SalariesPage /></ProtectedRoute>} />
        <Route path="/map" element={<ProtectedRoute><MapPage /></ProtectedRoute>} />
        <Route path="/bank-statements" element={<ProtectedRoute><BankStatementsPage /></ProtectedRoute>} />
        {/* Driver PWA routes (╨▒╨╡╨╖ ProtectedRoute тАФ ╤Б╨▓╨╛╤П ╨░╨▓╤В╨╛╤А╨╕╨╖╨░╤Ж╨╕╤П) */}
        <Route path="/driver/login" element={<DriverLoginPage />} />
        <Route path="/driver/dashboard" element={<DriverDashboardPage />} />
        <Route path="/driver" element={<Navigate to="/driver/dashboard" replace />} />
        <Route path="/driver/shift-report/:taskId" element={<ShiftReportPage />} />
        <Route path="/admin/dashboard" element={<ProtectedRoute><AdminDashboardPage /></ProtectedRoute>} />
        <Route path="/admin/gps" element={<ProtectedRoute><GpsAdminPage /></ProtectedRoute>} />
        {/* Catch-all тАФ ╨┤╨╛╨╗╨╢╨╡╨╜ ╨▒╤Л╤В╤М ╨┐╨╛╤Б╨╗╨╡╨┤╨╜╨╕╨╝ */}
        <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
    </Suspense>
  );
};

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Sentry.ErrorBoundary
      fallback={({ error }) => (
        <div style={{ padding: '20px', textAlign: 'center' }}>
          <h2>Что-то пошло не так</h2>
          <p>Произошла ошибка. Пожалуйста, обновите страницу.</p>
          <button onClick={() => window.location.reload()}>Обновить</button>
        </div>
      )}
    >
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
              iconTheme: { primary: '#10B981', secondary: '#fff' },
            },
            error: {
              duration: 5000,
              iconTheme: { primary: '#EF4444', secondary: '#fff' },
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
    </Sentry.ErrorBoundary>
  </React.StrictMode>
);
