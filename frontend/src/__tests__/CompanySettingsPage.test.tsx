import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import CompanySettingsPage from '../pages/CompanySettingsPage';

vi.mock('../components/Layout', () => ({
  default: ({ children }: any) => <div>{children}</div>,
}));
// Стабильная ссылка: иначе loadData пересоздаётся каждый рендер и циклует загрузку
const companyMock = vi.hoisted(() => ({
  currentCompany: { id: 1, name: 'Test Co' },
  currentCompanyId: 1,
}));
vi.mock('../contexts/CompanyContext', () => ({
  useCompany: () => companyMock,
}));
vi.mock('../api/companies', () => ({
  companiesApi: {
    getTaxSettings: vi.fn().mockResolvedValue({
      default_tax_system: 'usn_6',
      default_vat_rate: 0,
      default_is_vat_included: false,
    }),
    updateTaxSettings: vi.fn().mockResolvedValue({}),
  },
}));
vi.mock('../api/client', () => ({ default: { patch: vi.fn() } }));
vi.mock('../utils/toast', () => ({
  showToast: { success: vi.fn(), error: vi.fn() },
}));

describe('CompanySettingsPage — ставка по умолчанию', () => {
  it('переключение на ОСНО даёт 22, а не 20', async () => {
    render(<CompanySettingsPage />);
    fireEvent.click(await screen.findByText('💼 Налоги'));

    const systemSelect = screen.getByLabelText('Система налогообложения') as HTMLSelectElement;
    await waitFor(() => expect(systemSelect.value).toBe('usn_6'));

    fireEvent.change(systemSelect, { target: { value: 'osno' } });

    const rateSelect = screen.getByLabelText('Ставка НДС') as HTMLSelectElement;
    await waitFor(() => expect(rateSelect.value).toBe('22'));
  });
});
