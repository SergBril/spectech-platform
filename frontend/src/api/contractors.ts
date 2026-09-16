import apiClient from './client';

export interface BankDetails {
  account?: string | null;
  bank_name?: string | null;
  bik?: string | null;
  correspondent_account?: string | null;
}

export interface Contractor {
  id: number;
  type: 'client' | 'owner' | 'subcontractor';
  name: string;
  inn?: string | null;
  kpp?: string | null;
  ogrn?: string | null;
  legal_address?: string | null;
  actual_address?: string | null;
  bank_details?: BankDetails | null;
  contact_name?: string | null;
  contact_phone?: string | null;
  contact_email?: string | null;
  tax_system?: string | null;
  company_id?: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ContractorCreate {
  type: string;
  name: string;
  inn?: string | null;
  kpp?: string | null;
  ogrn?: string | null;
  legal_address?: string | null;
  actual_address?: string | null;
  bank_details?: BankDetails | null;
  contact_name?: string | null;
  contact_phone?: string | null;
  contact_email?: string | null;
  tax_system?: string | null;
}

export interface ContractorUpdate {
  type?: string | null;
  name?: string | null;
  inn?: string | null;
  kpp?: string | null;
  ogrn?: string | null;
  legal_address?: string | null;
  actual_address?: string | null;
  bank_details?: BankDetails | null;
  contact_name?: string | null;
  contact_phone?: string | null;
  contact_email?: string | null;
  tax_system?: string | null;
  is_active?: boolean | null;
}

export const contractorsApi = {
  getAll: async (params?: {
    type?: string;
    is_active?: boolean;
    offset?: number;
    limit?: number;
  }): Promise<Contractor[]> => {
    const response = await apiClient.get('/contractors', { params });
    return response.data;
  },

  getById: async (id: number): Promise<Contractor> => {
    const response = await apiClient.get(`/contractors/${id}`);
    return response.data;
  },

  create: async (data: ContractorCreate): Promise<Contractor> => {
    const response = await apiClient.post('/contractors', data);
    return response.data;
  },

  update: async (id: number, data: ContractorUpdate): Promise<Contractor> => {
    const response = await apiClient.patch(`/contractors/${id}`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/contractors/${id}`);
  },
};
