import apiClient from './client';

export interface Reconciliation {
  id: number;
  shift_task_id: number;

  // Operator data
  operator_moto_hours: number | null;
  operator_odometer: number | null;
  operator_fuel_used: number | null;

  // Telematics data
  telematics_moto_hours: number | null;
  telematics_odometer: number | null;
  telematics_fuel_used: number | null;
  telematics_data_points_count: number;

  // Planned data
  planned_moto_hours: number | null;
  planned_odometer: number | null;

  // Differences
  moto_hours_diff_percent: number | null;
  odometer_diff_percent: number | null;
  fuel_diff_percent: number | null;

  // Status
  reconciliation_status: 'pending' | 'auto_approved' | 'discrepancy_detected' | 'manual_review' | 'resolved';

  // Final values
  final_moto_hours: number | null;
  final_odometer: number | null;
  final_fuel_used: number | null;

  // Decision
  decision_source: 'operator' | 'telematics' | 'average' | 'manual' | null;
  decision_comment: string | null;
  decided_by: number | null;
  decided_at: string | null;

  company_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface ResolveReconciliationRequest {
  decision_source: 'operator' | 'telematics' | 'average' | 'manual';
  final_moto_hours?: number;
  final_odometer?: number;
  final_fuel_used?: number;
  decision_comment?: string;
}

export interface GenerateInvoiceFromReconciliationRequest {
  reconciliation_id: number;
  invoice_date?: string;
  due_date?: string;
  include_fuel_compensation?: boolean;
  vat_rate?: number;
}

export interface FinanceDashboard {
  period: {
    start: string;
    end: string;
  };
  revenue: {
    total: number;
    paid: number;
    outstanding: number;
  };
  expenses: {
    total: number;
    payouts: number;
    commission: number;
  };
  profit: {
    gross: number;
    net: number;
    margin_percent: number;
  };
  metrics: {
    invoices_count: number;
    avg_invoice: number;
    payouts_count: number;
    moto_hours_total: number;
  };
}

export interface ClientRevenue {
  client_id: number;
  client_name: string;
  total_revenue: number;
  invoices_count: number;
}

export interface VehicleRevenue {
  vehicle_id: number;
  vehicle_name: string;
  moto_hours: number;
  shifts_count: number;
}

export const reconciliationApi = {
  // === СПИСОК СВЕРОК ===
  getReconciliations: async (params?: {
    status?: string;
    date_from?: string;
    date_to?: string;
    shift_task_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<Reconciliation[]> => {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.append('status', params.status);
    if (params?.date_from) searchParams.append('date_from', params.date_from);
    if (params?.date_to) searchParams.append('date_to', params.date_to);
    if (params?.shift_task_id) searchParams.append('shift_task_id', params.shift_task_id.toString());
    if (params?.limit) searchParams.append('limit', params.limit.toString());
    if (params?.offset) searchParams.append('offset', params.offset.toString());

    const response = await apiClient.get(`/finance/reconciliations?${searchParams}`);
    return response.data;
  },

  // === ДЕТАЛИ СВЕРКИ ===
  getReconciliation: async (id: number): Promise<Reconciliation> => {
    const response = await apiClient.get(`/finance/reconciliations/${id}`);
    return response.data;
  },

  // === РАЗРЕШЕНИЕ КОНФЛИКТА ===
  resolveReconciliation: async (id: number, data: ResolveReconciliationRequest): Promise<Reconciliation> => {
    const response = await apiClient.post(`/finance/reconciliations/${id}/resolve`, data);
    return response.data;
  },

  // === ГЕНЕРАЦИЯ СЧЁТА ИЗ СВЕРКИ ===
  generateInvoice: async (data: GenerateInvoiceFromReconciliationRequest): Promise<any> => {
    const response = await apiClient.post('/finance/invoices/generate-from-reconciliation', data);
    return response.data;
  },

  // === СКАЧАТЬ PDF СВЕРКИ ===
  downloadPdf: async (id: number): Promise<Blob> => {
    const response = await apiClient.get(`/finance/reconciliation/${id}/pdf`, {
      responseType: 'blob',
    });
    return response.data;
  },

  // === СТАТИСТИКА ===
  getStats: async (params?: {
    date_from?: string;
    date_to?: string;
  }): Promise<{
    total: number;
    pending: number;
    auto_approved: number;
    manual_review: number;
    resolved: number;
  }> => {
    const searchParams = new URLSearchParams();
    if (params?.date_from) searchParams.append('date_from', params.date_from);
    if (params?.date_to) searchParams.append('date_to', params.date_to);

    const response = await apiClient.get(`/finance/reconciliations/stats?${searchParams}`);
    return response.data;
  },
};

export default reconciliationApi;
