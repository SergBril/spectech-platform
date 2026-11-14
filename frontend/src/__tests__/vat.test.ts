import { describe, it, expect } from 'vitest';
import { VAT_22_FROM_DATE, vatRateForDate, vatRateOnSystemChange } from '../utils/vat';

describe('vatRateForDate', () => {
  it('граница перехода вынесена в одну константу', () => {
    expect(VAT_22_FROM_DATE).toBe('2026-01-01');
  });

  it('2025-12-31 → 20%', () => {
    expect(vatRateForDate('2025-12-31')).toBe('20');
  });

  it('2026-01-01 → 22% (граница включительно)', () => {
    expect(vatRateForDate('2026-01-01')).toBe('22');
  });

  it('2026-11-13 → 22%', () => {
    expect(vatRateForDate('2026-11-13')).toBe('22');
  });

  it('2024-06-01 → 20%', () => {
    expect(vatRateForDate('2024-06-01')).toBe('20');
  });

  it('пустая дата → текущая эпоха (22)', () => {
    expect(vatRateForDate('')).toBe('22');
    expect(vatRateForDate(null)).toBe('22');
    expect(vatRateForDate(undefined)).toBe('22');
  });
});

describe('vatRateOnSystemChange', () => {
  it('переключение на ОСНО с нуля даёт 22 (не 20)', () => {
    expect(vatRateOnSystemChange('osno', 0)).toBe(22);
  });

  it('ОСНО сохраняет ненулевую выбранную ставку', () => {
    expect(vatRateOnSystemChange('osno', 20)).toBe(20);
    expect(vatRateOnSystemChange('osno', 22)).toBe(22);
  });

  it('не-ОСНО → 0', () => {
    expect(vatRateOnSystemChange('usn_6', 22)).toBe(0);
    expect(vatRateOnSystemChange('patent', 20)).toBe(0);
  });
});
