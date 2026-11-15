import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import type { ReactNode } from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import EdoSettingsPage from '../pages/EdoSettingsPage';
import apiClient from '../api/client';

vi.mock('../components/Layout', () => ({
  default: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));
vi.mock('../api/client', () => ({
  default: { get: vi.fn(), put: vi.fn() },
}));

const mockedClient = apiClient as unknown as { get: Mock; put: Mock };

const serverSettings = {
  operator: 'diadoc',
  diadoc_api_key: '****abcd',
  diadoc_api_key_set: true,
  diadoc_box_id: 'box-123',
  diadoc_use_sandbox: true,
  sbis_token: '****wxyz',
  sbis_token_set: true,
  sbis_client_id: 'client-77',
  auto_send_on_sign: false,
  default_format: 'upd_5_03',
};

const saveButton = () => screen.getByRole('button', { name: /Сохранить/ });

describe('EdoSettingsPage — рабочий URL, видимые ошибки, секреты через маску', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedClient.get.mockResolvedValue({ data: serverSettings });
    mockedClient.put.mockResolvedValue({ data: { message: 'EDO settings updated' } });
  });

  it('загружает настройки по /edo-settings (не /companies/edo-settings)', async () => {
    render(<EdoSettingsPage />);
    await screen.findByDisplayValue('box-123');
    expect(mockedClient.get).toHaveBeenCalledWith('/edo-settings');
    expect(mockedClient.get).not.toHaveBeenCalledWith('/companies/edo-settings');
  });

  it('ошибка загрузки видна, сохранение заблокировано, повтор работает', async () => {
    mockedClient.get.mockRejectedValueOnce({
      response: { data: { detail: 'Company not found' } },
    });
    render(<EdoSettingsPage />);

    expect(await screen.findByText(/Company not found/)).toBeInTheDocument();
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Сохранить/ })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Повторить загрузку' }));
    await screen.findByDisplayValue('box-123');
    expect(saveButton()).toBeInTheDocument();
  });

  it('маска не попадает в value полей ввода, бейдж показывает маску', async () => {
    render(<EdoSettingsPage />);
    expect(await screen.findByText('🔑 Ключ задан (****abcd)')).toBeInTheDocument();

    const newKey = screen.getByLabelText('Новый ключ') as HTMLInputElement;
    expect(newKey.value).toBe('');
    expect(newKey.value).not.toContain('****');

    fireEvent.click(screen.getByRole('radio', { name: /СБИС/ }));
    expect(screen.getByText('🔑 Токен задан (****wxyz)')).toBeInTheDocument();
    const newToken = screen.getByLabelText('Новый токен') as HTMLInputElement;
    expect(newToken.value).toBe('');
  });

  it('ввод нового ключа → PUT /edo-settings содержит новый ключ', async () => {
    render(<EdoSettingsPage />);
    await screen.findByDisplayValue('box-123');

    fireEvent.change(screen.getByLabelText('Новый ключ'), {
      target: { value: 'new-secret-key' },
    });
    fireEvent.click(saveButton());

    await waitFor(() => expect(mockedClient.put).toHaveBeenCalled());
    expect(mockedClient.put).toHaveBeenCalledWith(
      '/edo-settings',
      expect.objectContaining({ diadoc_api_key: 'new-secret-key' })
    );
    expect(await screen.findByText(/Настройки ЭДО сохранены/)).toBeInTheDocument();
  });

  it('«Удалить ключ» → PUT с пустой строкой', async () => {
    render(<EdoSettingsPage />);
    await screen.findByDisplayValue('box-123');

    fireEvent.click(screen.getByRole('button', { name: 'Удалить ключ' }));

    await waitFor(() =>
      expect(mockedClient.put).toHaveBeenCalledWith('/edo-settings', {
        diadoc_api_key: '',
      })
    );
  });

  it('«Удалить токен» СБИС → PUT с пустой строкой', async () => {
    render(<EdoSettingsPage />);
    await screen.findByDisplayValue('box-123');
    fireEvent.click(screen.getByRole('radio', { name: /СБИС/ }));

    fireEvent.click(screen.getByRole('button', { name: 'Удалить токен' }));

    await waitFor(() =>
      expect(mockedClient.put).toHaveBeenCalledWith('/edo-settings', {
        sbis_token: '',
      })
    );
  });

  it('сохранение без изменения ключа → секретов нет в payload', async () => {
    render(<EdoSettingsPage />);
    await screen.findByDisplayValue('box-123');

    fireEvent.click(saveButton());

    await waitFor(() => expect(mockedClient.put).toHaveBeenCalled());
    const [url, payload] = mockedClient.put.mock.calls[0];
    expect(url).toBe('/edo-settings');
    expect(payload).not.toHaveProperty('diadoc_api_key');
    expect(payload).not.toHaveProperty('sbis_token');
    expect(payload).toMatchObject({
      operator: 'diadoc',
      diadoc_box_id: 'box-123',
      diadoc_use_sandbox: true,
      sbis_client_id: 'client-77',
      auto_send_on_sign: false,
      default_format: 'upd_5_03',
    });
  });

  it('выключенная песочница показывает предупреждение о боевом контуре', async () => {
    mockedClient.get.mockResolvedValue({
      data: { ...serverSettings, diadoc_use_sandbox: false },
    });
    render(<EdoSettingsPage />);
    expect(await screen.findByText(/БОЕВОЙ Диадок/)).toBeInTheDocument();
    expect(screen.getByText(/настоящие документы/)).toBeInTheDocument();
  });

  it('включение песочки убирает предупреждение, выключение — возвращает', async () => {
    render(<EdoSettingsPage />);
    await screen.findByDisplayValue('box-123');
    expect(screen.queryByText(/БОЕВОЙ Диадок/)).not.toBeInTheDocument();

    const sandbox = screen.getByLabelText(/Использовать песочницу/);
    fireEvent.click(sandbox);
    expect(screen.getByText(/БОЕВОЙ Диадок/)).toBeInTheDocument();

    fireEvent.click(sandbox);
    expect(screen.queryByText(/БОЕВОЙ Диадок/)).not.toBeInTheDocument();
  });
});
