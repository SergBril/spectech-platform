import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import apiClient from '../api/client';
import { financeApi } from '../api/finance';

vi.mock('../api/client', () => ({
  default: { post: vi.fn(), get: vi.fn() },
}));

const mockedClient = apiClient as unknown as { post: Mock; get: Mock };

// RC-7: тип verifyUpdSignature приведён к фактическому ответу обработчика
// {valid, provider, signed_at} (или {valid:false, message}). Полей размеров
// xml_size/sig_size в ответе нет - они не добавляются ради типа.
describe('financeApi.verifyUpdSignature — форма ответа обработчика', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('возвращает {valid, provider, signed_at} без полей размеров', async () => {
    mockedClient.get.mockResolvedValue({
      data: { valid: true, provider: 'КриптоПро', signed_at: '2026-11-20T10:00:00' },
    });
    const result = await financeApi.verifyUpdSignature(42);
    expect(mockedClient.get).toHaveBeenCalledWith('/shifts/acts/42/verify-signature');
    expect(result.valid).toBe(true);
    expect(result.provider).toBe('КриптоПро');
    expect(result.signed_at).toBe('2026-11-20T10:00:00');
    expect(result).not.toHaveProperty('xml_size');
    expect(result).not.toHaveProperty('sig_size');
  });

  it('неподписанный акт возвращает {valid:false, message}', async () => {
    mockedClient.get.mockResolvedValue({
      data: { valid: false, message: 'Акт не подписан' },
    });
    const result = await financeApi.verifyUpdSignature(7);
    expect(result.valid).toBe(false);
    expect(result.message).toBe('Акт не подписан');
  });
});
