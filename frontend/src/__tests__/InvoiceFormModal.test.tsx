import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { InvoiceFormModal } from '../components/InvoiceFormModal';

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

const renderModal = (invoice: any = null) =>
  render(<InvoiceFormModal invoice={invoice} onClose={() => {}} onSave={vi.fn()} />);

const rateSelect = () => screen.getByLabelText('Ставка НДС') as HTMLSelectElement;

describe('InvoiceFormModal — автоподбор ставки НДС по дате документа', () => {
  it('смена даты на 2025-12-31 даёт ставку 20', async () => {
    renderModal();
    fireEvent.change(screen.getByLabelText('Дата счёта'), {
      target: { value: '2025-12-31' },
    });
    await waitFor(() => expect(rateSelect().value).toBe('20'));
  });

  it('смена даты на 2026-01-01 даёт ставку 22', async () => {
    renderModal();
    fireEvent.change(screen.getByLabelText('Дата счёта'), {
      target: { value: '2025-12-31' },
    });
    await waitFor(() => expect(rateSelect().value).toBe('20'));
    fireEvent.change(screen.getByLabelText('Дата счёта'), {
      target: { value: '2026-01-01' },
    });
    await waitFor(() => expect(rateSelect().value).toBe('22'));
  });

  it('ручной выбор 20 при дате 2026 НЕ перетирается сменой даты', async () => {
    renderModal();
    fireEvent.change(screen.getByLabelText('Дата счёта'), {
      target: { value: '2026-06-01' },
    });
    await waitFor(() => expect(rateSelect().value).toBe('22'));

    fireEvent.change(rateSelect(), { target: { value: '20' } });
    await waitFor(() => expect(rateSelect().value).toBe('20'));

    fireEvent.change(screen.getByLabelText('Дата счёта'), {
      target: { value: '2026-12-01' },
    });
    // ручной выбор приоритетнее автоподбора
    await waitFor(() => expect(rateSelect().value).toBe('20'));
  });

  it('редактирование: ставка существующего документа сохраняется', async () => {
    renderModal({
      id: 1,
      document_number: 'INV-1',
      vat_rate: '20',
      tax_system: 'osno',
      invoice_date: '2025-12-15',
      is_vat_included: true,
      items: [],
    });
    await waitFor(() => expect(rateSelect().value).toBe('20'));
    fireEvent.change(screen.getByLabelText('Дата счёта'), {
      target: { value: '2026-06-01' },
    });
    await waitFor(() => expect(rateSelect().value).toBe('20'));
  });
});
