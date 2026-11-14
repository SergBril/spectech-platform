import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { TaxSystemSelector } from '../components/TaxSystemSelector';

describe('TaxSystemSelector', () => {
  it('20% остаётся выбираемым (нужно для документов за 2025)', () => {
    render(<TaxSystemSelector value="osno" onChange={() => {}} />);
    const rateSelect = screen.getByLabelText('Ставка НДС');
    const values = Array.from(rateSelect.querySelectorAll('option')).map((o) => o.value);
    expect(values).toContain('20');
    expect(values).toContain('22');
  });

  it('ручной выбор ставки вызывает onVatRateChange', () => {
    const onVatRateChange = vi.fn();
    render(
      <TaxSystemSelector value="osno" onChange={() => {}} onVatRateChange={onVatRateChange} />,
    );
    fireEvent.change(screen.getByLabelText('Ставка НДС'), { target: { value: '20' } });
    expect(onVatRateChange).toHaveBeenCalledWith('20');
  });

  it('контролируемая ставка отображается (синхронизация с родителем)', () => {
    render(<TaxSystemSelector value="osno" vatRate="20" onChange={() => {}} />);
    expect((screen.getByLabelText('Ставка НДС') as HTMLSelectElement).value).toBe('20');
  });

  it('в контролируемом режиме смена системы не стреляет onVatRateChange', () => {
    const onChange = vi.fn();
    const onVatRateChange = vi.fn();
    render(
      <TaxSystemSelector
        value="usn_6"
        vatRate="0"
        onChange={onChange}
        onVatRateChange={onVatRateChange}
      />,
    );
    fireEvent.change(screen.getByLabelText('Система налогообложения'), {
      target: { value: 'osno' },
    });
    expect(onChange).toHaveBeenCalledWith('osno');
    expect(onVatRateChange).not.toHaveBeenCalled();
  });
});
