import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import type { ReactNode } from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import GpsAdminPage from '../pages/admin/GpsAdminPage';

vi.mock('../components/Layout', () => ({
  default: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));
vi.mock('react-hot-toast', () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));

const vehicleRow = {
  id: 7,
  name: 'GPS Truck',
  gps_provider: 'mapix',
  // Пароль с сервера больше не приходит — только флаг наличия.
  gps_provider_config: {
    login: 'fleet',
    api_url: 'https://gps.mapix.su',
    object_ids: ['12345'],
    password_set: true,
  },
  last_point_at: null,
  total_points: 3,
};

const fetchMock = () => globalThis.fetch as unknown as Mock;

const patchBodies = () =>
  fetchMock()
    .mock.calls.filter(([, init]) => (init as RequestInit | undefined)?.method === 'PATCH')
    .map(([, init]) => JSON.parse((init as RequestInit).body as string));

describe('GpsAdminPage — сохранённый пароль не затирается пустым полем', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string, init?: RequestInit) => {
        if (init?.method === 'PATCH') {
          return Promise.resolve({ ok: true, json: async () => ({}) });
        }
        if (String(url).includes('/points/stats')) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              total_points: 3,
              vehicles_with_data: 1,
              latest_recorded_at: null,
              oldest_recorded_at: null,
            }),
          });
        }
        return Promise.resolve({ ok: true, json: async () => [vehicleRow] });
      }),
    );
  });

  const openEditor = async () => {
    render(<GpsAdminPage />);
    // Имя есть и в <option> фильтра экспорта, и в ячейке таблицы — берём ячейку.
    await screen.findByRole('cell', { name: 'GPS Truck' });
    fireEvent.click(screen.getByRole('button', { name: 'Настроить' }));
    return (await screen.findByPlaceholderText(
      'сохранён — введите для замены',
    )) as HTMLInputElement;
  };

  it('поле пароля пустое: сервер его не отдаёт', async () => {
    const input = await openEditor();
    expect(input.value).toBe('');
  });

  it('сохранение с пустым паролем НЕ отправляет ключ password', async () => {
    await openEditor();
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }));

    await waitFor(() => expect(patchBodies().length).toBe(1));
    const cfg = patchBodies()[0].gps_provider_config;
    expect(cfg).not.toHaveProperty('password');
    expect(cfg.login).toBe('fleet');
  });

  it('введённый пароль отправляется', async () => {
    const input = await openEditor();
    fireEvent.change(input, { target: { value: 'rotated' } });
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }));

    await waitFor(() => expect(patchBodies().length).toBe(1));
    expect(patchBodies()[0].gps_provider_config.password).toBe('rotated');
  });
});

describe('GpsAdminPage — placeholder говорит правду о наличии пароля', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string, init?: RequestInit) => {
        if (init?.method === 'PATCH') {
          return Promise.resolve({ ok: true, json: async () => ({}) });
        }
        if (String(url).includes('/points/stats')) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              total_points: 3,
              vehicles_with_data: 1,
              latest_recorded_at: null,
              oldest_recorded_at: null,
            }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: async () => [
            {
              ...vehicleRow,
              gps_provider_config: { login: 'fleet', api_url: 'https://x' },
            },
          ],
        });
      }),
    );
  });

  it('пароля нет → поле не обещает, что он сохранён', async () => {
    render(<GpsAdminPage />);
    await screen.findByRole('cell', { name: 'GPS Truck' });
    fireEvent.click(screen.getByRole('button', { name: 'Настроить' }));

    expect(await screen.findByPlaceholderText('Пароль не задан')).toBeInTheDocument();
    expect(
      screen.queryByPlaceholderText('сохранён — введите для замены'),
    ).not.toBeInTheDocument();
  });
});
