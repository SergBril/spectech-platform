import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { ReactNode } from 'react';
import { render, screen, fireEvent } from '@testing-library/react';

vi.mock('../api/client', () => ({
  default: {
    get: vi.fn().mockResolvedValue({
      data: {
        summary: { total_vehicles: 0, avg_utilization_pct: 0, total_shifts: 0, total_hours: 0 },
        vehicles: [],
      },
    }),
    post: vi.fn(),
  },
}));
vi.mock('../components/Layout', () => ({
  default: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

import UtilizationPage from '../pages/UtilizationPage';

// RC-8: кнопка «Выгрузка 1С» звала /shifts/export/1c-acts (404). Реальный
// маршрут - /shifts/acts/export/1c; период страницы (date_from/date_to)
// обязателен для обработчика и уже передаётся.
describe('UtilizationPage — кнопка «Выгрузка 1С»', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('открывает реальный маршрут /shifts/acts/export/1c с периодом страницы', async () => {
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null);
    render(<UtilizationPage />);
    const button = await screen.findByText(/Выгрузка 1С/);
    fireEvent.click(button);

    expect(openSpy).toHaveBeenCalledTimes(1);
    const url = openSpy.mock.calls[0][0] as string;
    expect(url).toMatch(
      /^\/api\/v1\/shifts\/acts\/export\/1c\?date_from=\d{4}-\d{2}-\d{2}&date_to=\d{4}-\d{2}-\d{2}$/,
    );
    expect(url).not.toContain('/shifts/export/1c-acts');
    openSpy.mockRestore();
  });
});
