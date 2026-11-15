import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { ReactNode } from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import type { Act } from '../api/finance';
import type { Request } from '../api/requests';

vi.mock('../api/requests', () => ({
  requestsApi: { getById: vi.fn(), getHistory: vi.fn() },
}));
vi.mock('../api/finance', () => ({
  financeApi: {
    getInvoices: vi.fn(),
    getActs: vi.fn(),
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
vi.mock('../components/FileUploadButton', () => ({ FileUploadButton: () => null }));
vi.mock('../components/FileList', () => ({ FileList: () => null }));
vi.mock('../utils/toast', () => ({ showToast: { success: vi.fn(), error: vi.fn() } }));
vi.mock('react-router-dom', () => ({
  useParams: () => ({ id: '1' }),
  useNavigate: () => vi.fn(),
}));

import RequestDetailPage from '../pages/RequestDetailPage';
import { financeApi } from '../api/finance';
import { requestsApi } from '../api/requests';

const mockedFinance = vi.mocked(financeApi);
const mockedRequests = vi.mocked(requestsApi);

const requestFixture: Request = {
  id: 1,
  client_id: 5,
  status: 'new',
  request_type: 'one_time',
  vehicle_category_id: null,
  work_type: 'Земляные работы',
  object_address: 'Москва, ул Тверская, д 1',
  planned_start: '2026-05-20T08:00:00Z',
  planned_end: '2026-05-20T18:00:00Z',
  actual_start: null,
  actual_end: null,
  shift_duration_hours: 8,
  client_rate: 15250,
  rate_type: 'hourly',
  estimated_amount: 122000,
  final_amount: null,
  assigned_vehicle_id: null,
  assigned_operator_id: null,
  source_channel: 'phone',
  priority: 'normal',
  comment: null,
  created_at: '2026-05-19T10:00:00Z',
  client_name: 'ООО Ромашка',
};

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

describe('RequestDetailPage — кнопки ЭДО открывают DiadocSendModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedRequests.getById.mockResolvedValue(requestFixture);
    mockedRequests.getHistory.mockResolvedValue([]);
    mockedFinance.getInvoices.mockResolvedValue([]);
    mockedFinance.getActs.mockResolvedValue([actFixture]);
    mockedFinance.getDiadocCounterparties.mockResolvedValue([
      { box_id: 'box-1', name: 'ООО Ромашка', inn: '7701234567' },
    ]);
  });

  it('клик по 📤ЭДО открывает модалку выбора контрагента вместо confirm()', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);

    render(<RequestDetailPage />);

    const edoButtons = await screen.findAllByTitle('Диадок');
    expect(edoButtons).toHaveLength(2);

    fireEvent.click(edoButtons[0]);

    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Отправить акт в Diadoc/ })).toBeInTheDocument();
    expect(await screen.findByText('ООО Ромашка (ИНН: 7701234567)')).toBeInTheDocument();
    expect(confirmSpy).not.toHaveBeenCalled();

    confirmSpy.mockRestore();
  });
});
