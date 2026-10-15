import { lazy } from 'react';

// Ленивая загрузка тяжёлых страниц
export const DashboardPage = lazy(() => import('./DashboardPage'));
export const FinancePage = lazy(() => import('./FinancePage'));
export const CompanyProfilePage = lazy(() => import('./CompanyProfilePage'));
export const MarketplacePage = lazy(() => import('./MarketplacePage'));
export const VehiclesPage = lazy(() => import('./VehiclesPage'));
export const RequestsPage = lazy(() => import('./RequestsPage'));
export const ContractorsPage = lazy(() => import('./ContractorsPage'));
export const ContractorDetailPage = lazy(() => import('./ContractorDetailPage'));
export const MaintenancePage = lazy(() => import('./MaintenancePage'));
export const MaintenanceDetailPage = lazy(() => import('./MaintenanceDetailPage'));
export const MaintenanceCreatePage = lazy(() => import('./MaintenanceCreatePage'));
export const MaintenanceAnalyticsPage = lazy(() => import('./MaintenanceAnalyticsPage'));
export const FuelAnalyticsPage = lazy(() => import('./FuelAnalyticsPage'));
export const ReconciliationPage = lazy(() => import('./ReconciliationPage'));
export const InvoicesPage = lazy(() => import('./InvoicesPage'));
export const EmailTemplatesPage = lazy(() => import('./EmailTemplatesPage'));
export const EmailLogsPage = lazy(() => import('./EmailLogsPage'));
export const CompanySettingsPage = lazy(() => import('./CompanySettingsPage'));
export const MyListingsPage = lazy(() => import('./MyListingsPage'));
export const RequestDetailPage = lazy(() => import('./RequestDetailPage'));
export const ActCreatePage = lazy(() => import('./ActCreatePage'));
export const VehicleDetailPage = lazy(() => import('./VehicleDetailPage'));

// Лёгкие страницы — без lazy (загружаются сразу)
// LoginPage, RegisterPage — маленькие, нужны быстро
export const DriversPage = lazy(() => import('./DriversPage'));
