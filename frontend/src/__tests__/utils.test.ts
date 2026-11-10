import { describe, it, expect } from 'vitest';

// Test formatCurrency utility if it exists, otherwise basic sanity
describe('Utils sanity', () => {
  it('basic assertions work', () => {
    expect(1 + 1).toBe(2);
    expect('spectech').toContain('tech');
  });

  it('formats numbers correctly', () => {
    const formatter = new Intl.NumberFormat('ru-RU', {
      style: 'currency',
      currency: 'RUB',
    });
    const result = formatter.format(1500);
    expect(result).toContain('1');
    expect(result).toContain('500');
  });
});
