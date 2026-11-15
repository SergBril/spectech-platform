import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import DiadocSendModal from '../components/DiadocSendModal';
import { financeApi } from '../api/finance';

vi.mock('../api/finance', () => ({
  financeApi: {
    getDiadocCounterparties: vi.fn(),
    sendToDiadoc: vi.fn(),
  },
}));

const mockedApi = vi.mocked(financeApi);

const counterparties = [
  { box_id: 'box-1', name: 'ООО Ромашка', inn: '7701234567' },
  { box_id: 'box-2', name: 'ООО Василёк', inn: '7709876543' },
];

const sendButton = () => screen.getByRole('button', { name: /Отправить/ });
const counterpartySelect = () => screen.getByLabelText('Контрагент') as HTMLSelectElement;

describe('DiadocSendModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.getDiadocCounterparties.mockResolvedValue(counterparties);
    mockedApi.sendToDiadoc.mockResolvedValue({
      message: 'Акт отправлен через Diadoc',
      message_id: 'msg-1',
      status: 'sent',
    });
  });

  it('загружает контрагентов и показывает их в списке', async () => {
    render(<DiadocSendModal actId={42} onClose={vi.fn()} onSent={vi.fn()} />);
    expect(await screen.findByText('ООО Ромашка (ИНН: 7701234567)')).toBeInTheDocument();
    expect(screen.getByText('ООО Василёк (ИНН: 7709876543)')).toBeInTheDocument();
    expect(mockedApi.getDiadocCounterparties).toHaveBeenCalledTimes(1);
  });

  it('без выбора box кнопка отправки disabled', async () => {
    render(<DiadocSendModal actId={42} onClose={vi.fn()} onSent={vi.fn()} />);
    await screen.findByText('ООО Ромашка (ИНН: 7701234567)');
    expect(sendButton()).toBeDisabled();
  });

  it('отправка шлёт actId и выбранный box, успешный ответ показывает message', async () => {
    const onSent = vi.fn();
    render(<DiadocSendModal actId={42} onClose={vi.fn()} onSent={onSent} />);
    await screen.findByText('ООО Ромашка (ИНН: 7701234567)');

    fireEvent.change(counterpartySelect(), { target: { value: 'box-1' } });
    expect(sendButton()).toBeEnabled();
    fireEvent.click(sendButton());

    await waitFor(() => expect(mockedApi.sendToDiadoc).toHaveBeenCalledWith(42, 'box-1'));
    expect(await screen.findByText('Акт отправлен через Diadoc')).toBeInTheDocument();
    expect(onSent).toHaveBeenCalledWith({
      message: 'Акт отправлен через Diadoc',
      message_id: 'msg-1',
      status: 'sent',
    });
  });

  it('ошибка отправки показывает detail и оставляет модалку открытой', async () => {
    mockedApi.sendToDiadoc.mockRejectedValue({
      response: { data: { detail: 'Diadoc authentication failed' } },
    });
    render(<DiadocSendModal actId={42} onClose={vi.fn()} onSent={vi.fn()} />);
    await screen.findByText('ООО Ромашка (ИНН: 7701234567)');
    fireEvent.change(counterpartySelect(), { target: { value: 'box-1' } });
    fireEvent.click(sendButton());

    expect(await screen.findByText(/Diadoc authentication failed/)).toBeInTheDocument();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(sendButton()).toBeEnabled();
  });

  it('пустой список контрагентов показывает предупреждение, отправка недоступна', async () => {
    mockedApi.getDiadocCounterparties.mockResolvedValue([]);
    render(<DiadocSendModal actId={42} onClose={vi.fn()} onSent={vi.fn()} />);
    expect(await screen.findByText(/Контрагенты не загружены/)).toBeInTheDocument();
    expect(sendButton()).toBeDisabled();
  });

  it('ошибка загрузки показывает предупреждение с кнопкой Повторить', async () => {
    mockedApi.getDiadocCounterparties.mockRejectedValueOnce(new Error('network down'));
    render(<DiadocSendModal actId={42} onClose={vi.fn()} onSent={vi.fn()} />);
    expect(await screen.findByText(/network down/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Повторить' }));
    expect(await screen.findByText('ООО Ромашка (ИНН: 7701234567)')).toBeInTheDocument();
  });

  it('Отмена и Escape закрывают модалку', async () => {
    const onClose = vi.fn();
    render(<DiadocSendModal actId={42} onClose={onClose} onSent={vi.fn()} />);
    await screen.findByText('ООО Ромашка (ИНН: 7701234567)');
    fireEvent.click(screen.getByRole('button', { name: 'Отмена' }));
    expect(onClose).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
