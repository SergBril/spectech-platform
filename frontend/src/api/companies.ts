import { apiClient } from './client';

export interface CompanyTaxSettings {
  default_tax_system: string;
  default_vat_rate: number;
  default_is_vat_included: boolean;
}

export const companiesApi = {
  getTaxSettings: async (companyId: number): Promise<CompanyTaxSettings> => {
    const response = await apiClient.get(`/companies/${companyId}/tax-settings`);
    return response.data;
  },

  updateTaxSettings: async (companyId: number, settings: CompanyTaxSettings): Promise<CompanyTaxSettings> => {
    const response = await apiClient.patch(`/companies/${companyId}/tax-settings`, settings);
    return response.data;
  },
};
