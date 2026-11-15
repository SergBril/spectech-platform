import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { ReactNode } from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import type { Act, PaymentsDashboard } from '../api/finance';

vi.mock('../api/finance', () => ({
  financeApi: {
    getDashboard: vi.fn(),
    getInvoices: vi.fn(),
    getActs: vi.fn(),
    getPayouts: vi.fn(),
    getFinanceDashboardV2: vi.fn(),
    getDiadocCounterparties: vi.fn(),
    sendToDiadoc: vi.fn(),
  },
}));
vi.mock('../api/export', () => ({ exportApi: {}, downloadBlob: vi.fn() }));
vi.mock('../api/client', () => ({
  default: { get: vi.fn().mockResolvedValue({ data: [] }), post: vi.fn() },
}));
vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 1, email: 'test@test.com', company_id: 1 },
    logout: vi.fn(),
    hasPermission: () => true,
  }),
}));
vi.mock('../components/Layout', () => ({
  default: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));
vi.mock('../components/NotificationBell', () => ({ default: () => null }));
vi.mock('../components/FinancialCharts', () => ({ default: () => null }));
vi.mock('../utils/toast', () => ({ showToast: { success: vi.fn(), error: vi.fn() } }));
vi.mock('react-router-dom', () => ({ useNavigate: () => vi.fn() }));

import FinancePage from '../pages/FinancePage';
import { financeApi } from '../api/finance';

const mockedApi = vi.mocked(financeApi);

const actFixture: Act = {
  id: 101,
  document_number: 'ACT-AP-001',
  request_id: 1,
  client_id: 5,
  company_id: 1,
  total_amount: '122000.00',
  act_date: '2026-05-20',
  status: 'draft',
  signed_by_client_at: null,
  signed_by_executor_at: null,
  pdf_url: null,
  comment: null,
  created_at: '2026-05-20T10:00:00Z',
  updated_at: '2026-05-20T10:00:00Z',
  tax_system: 'osno',
  vat_rate: '22',
  is_vat_included: true,
};

const dashboardFixture: PaymentsDashboard = {
  total_revenue: '122000.00',
  total_paid: '0.00',
  total_outstanding: '122000.00',
  total_commission_earned: '0.00',
  invoices_count: 0,
  acts_count: 1,
  payouts_count: 0,
};

describe('FinancePage — кнопки ЭДО открывают DiadocSendModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.getDashboard.mockResolvedValue(dashboardFixture);
    mockedApi.getInvoices.mockResolvedValue([]);
    mockedApi.getActs.mockResolvedValue([actFixture]);
    mockedApi.getPayouts.mockResolvedValue([]);
    mockedApi.getFinanceDashboardV2.mockRejectedValue(new Error('v2 недоступен в тесте'));
    mockedApi.getDiadocCounterparties.mockResolvedValue([
      { box_id: 'box-1', name: 'ООО Ромашка', inn: '7701234567' },
    ]);
  });

  it('клик по 📤ЭДО открывает модалку выбора контрагента вместо confirm()', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);

    render(<FinancePage />);
    fireEvent.click(await screen.findByText('Акты (1)'));

    const edoButtons = await screen.findAllByTitle(/Диадок/);
    expect(edoButtons).toHaveLength(4);

    fireEvent.click(edoButtons[0]);

    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Отправить акт в Diadoc/ })).toBeInTheDocument();
    expect(await screen.findByText('ООО Ромашка (ИНН: 7701234567)')).toBeInTheDocument();
    expect(confirmSpy).not.toHaveBeenCalled();

    confirmSpy.mockRestore();
  });
});
