import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ActFormModal } from '../components/ActFormModal';

vi.mock('../api/companies', () => ({
  companiesApi: {
    getTaxSettings: vi.fn().mockResolvedValue({
      default_tax_system: 'osno',
      default_vat_rate: 22,
      default_is_vat_included: true,
    }),
  },
}));
vi.mock('../api/contractors', () => ({
  contractorsApi: { getAll: vi.fn().mockResolvedValue([]) },
}));
vi.mock('../api/requests', () => ({
  requestsApi: { getAll: vi.fn().mockResolvedValue([]) },
}));
vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ user: { company_id: 1 } }),
}));

const rateSelect = () => screen.getByLabelText('Ставка НДС') as HTMLSelectElement;

describe('ActFormModal — автоподбор ставки НДС по дате документа', () => {
  it('смена даты на 2025-12-31 даёт ставку 20', async () => {
    render(<ActFormModal act={null} onClose={() => {}} onSave={vi.fn()} />);
    fireEvent.change(screen.getByLabelText('Дата акта'), {
      target: { value: '2025-12-31' },
    });
    await waitFor(() => expect(rateSelect().value).toBe('20'));
  });

  it('ручной выбор 20 при дате 2026 НЕ перетирается сменой даты', async () => {
    render(<ActFormModal act={null} onClose={() => {}} onSave={vi.fn()} />);
    fireEvent.change(screen.getByLabelText('Дата акта'), {
      target: { value: '2026-06-01' },
    });
    await waitFor(() => expect(rateSelect().value).toBe('22'));

    fireEvent.change(rateSelect(), { target: { value: '20' } });
    await waitFor(() => expect(rateSelect().value).toBe('20'));

    fireEvent.change(screen.getByLabelText('Дата акта'), {
      target: { value: '2026-12-01' },
    });
    await waitFor(() => expect(rateSelect().value).toBe('20'));
  });
});
