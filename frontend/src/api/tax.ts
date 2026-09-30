import apiClient from './client';
export const taxApi = {
  /**
   * Получить конфигурацию для форм (системы + ставки НДС)
   */
  getConfig: async (): Promise<{
    systems: Array<{ value: string; label: string; has_vat: boolean }>;
    vat_rates: Array<{ value: string; label: string }>;
    default_system: string;
    default_vat_rate: string;
  }> => {
    const response = await apiClient.get('/tax/config');  // ← apiClient
    return response.data;
  },
};
