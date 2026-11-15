import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import apiClient from '../api/client';
import { financeApi } from '../api/finance';

vi.mock('../api/client', () => ({
  default: { post: vi.fn(), get: vi.fn() },
}));

// vi.mocked не выводит mock-тип для перегруженных методов axios
const mockedClient = apiClient as unknown as { post: Mock; get: Mock };

describe('financeApi — Diadoc (живой роут /shifts/diadoc)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('sendToDiadoc шлёт POST /shifts/diadoc/send-act с {act_id, counterparty_box_id}', async () => {
    mockedClient.post.mockResolvedValue({
      data: { message: 'Акт отправлен через Diadoc', status: 'sent', message_id: 'msg-1' },
    });
    const result = await financeApi.sendToDiadoc(42, 'box-1');
    expect(mockedClient.post).toHaveBeenCalledWith('/shifts/diadoc/send-act', {
      act_id: 42,
      counterparty_box_id: 'box-1',
    });
    expect(result.message).toBe('Акт отправлен через Diadoc');
  });

  it('getDiadocCounterparties запрашивает /shifts/diadoc/counterparties', async () => {
    mockedClient.get.mockResolvedValue({
      data: [{ box_id: 'box-1', name: 'ООО Ромашка', inn: '7701234567' }],
    });
    const list = await financeApi.getDiadocCounterparties();
    expect(mockedClient.get).toHaveBeenCalledWith('/shifts/diadoc/counterparties');
    expect(list).toHaveLength(1);
    expect(list[0].box_id).toBe('box-1');
  });

  it('getDiadocCounterparties возвращает [] для не-массива', async () => {
    mockedClient.get.mockResolvedValue({ data: null });
    const list = await financeApi.getDiadocCounterparties();
    expect(list).toEqual([]);
  });
});
