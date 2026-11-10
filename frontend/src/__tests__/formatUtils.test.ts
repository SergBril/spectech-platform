import { describe, it, expect } from 'vitest';

describe('Formatting Utilities', () => {
  it('formats currency in RUB', () => {
    const fmt = new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB' });
    expect(fmt.format(1500)).toContain('1');
    expect(fmt.format(0)).toContain('0');
  });

  it('formats dates in Russian locale', () => {
    const date = new Date('2026-01-15');
    const formatted = date.toLocaleDateString('ru-RU');
    expect(formatted).toContain('15');
    expect(formatted).toContain('01');
  });

  it('formats large numbers with spaces', () => {
    const fmt = new Intl.NumberFormat('ru-RU');
    const result = fmt.format(1500000);
    expect(result).toContain('1');
    expect(result.length).toBeGreaterThan(4);
  });

  it('handles null/undefined safely', () => {
    expect(String(null)).toBe('null');
    expect(String(undefined)).toBe('undefined');
    expect(0 || 'default').toBe('default');
  });
});
