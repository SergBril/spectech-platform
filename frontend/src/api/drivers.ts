import apiClient from './client';

export interface DriverProfile {
  contractor_id: number;
  full_name: string;
  position: string | null;
  user_id: number | null;
  hire_date: string | null;
  is_active: boolean;
  date_of_birth: string | null;
  passport_series: string | null;
  passport_number: string | null;
  passport_issued_by: string | null;
  passport_issue_date: string | null;
  license_number: string | null;
  license_category: string | null;
  license_issue_date: string | null;
  license_expiry_date: string | null;
  machinist_certificate: string | null;
  machinist_certificate_type: string | null;
  machinist_certificate_expiry: string | null;
  medical_cert_expiry: string | null;
  safety_training_expiry: string | null;
  notes: string | null;
}

export interface DriverListResponse {
  items: DriverProfile[];
  total: number;
}

export const driversApi = {
  async list(params?: { search?: string; limit?: number; skip?: number }): Promise<DriverListResponse> {
    const response = await apiClient.get<DriverListResponse>('/drivers', { params });
    return response.data;
  },

  async getById(contractorId: number): Promise<DriverProfile> {
    const response = await apiClient.get<DriverProfile>(`/drivers/${contractorId}`);
    return response.data;
  },

  async updateProfile(contractorId: number, data: Partial<DriverProfile>): Promise<{ message: string }> {
    const response = await apiClient.put(`/drivers/${contractorId}/profile`, data);
    return response.data;
  },
};