import apiClient from './client';

export type InvoiceStatus = 'draft' | 'sent' | 'paid' | 'partially_paid' | 'overdue' | 'cancelled';
export type ActStatus = 'draft' | 'sent' | 'paid' | 'overdue' | 'cancelled';
export type PayoutStatus = 'draft' | 'sent' | 'paid' | 'overdue' | 'cancelled';
export type PaymentMethod = 'bank_transfer' | 'cash' | 'card' | 'other';

export interface InvoiceItem {
  id?: number;
  description: string;
  quantity: number;
  unit_price: number;
  amount: number;
}

export interface InvoiceItemCreate {
  description: string;
  quantity: number;
  unit_price: number;
}

export interface Invoice {
  id: number;
  document_number: string;
  request_id: number | null;
  client_id: number | null;
  company_id: number | null;
  subtotal: string;
  vat_amount: string;
  vat_rate: string;
  total: string;
  paid_amount: string;
  invoice_date: string;
  due_date: string;
  status: InvoiceStatus;
  comment: string | null;
  items: InvoiceItem[];
  created_at: string;
  updated_at: string;
  // Добавьте эти поля:
  tax_system?: string;
  is_vat_included?: boolean;
}

export interface InvoiceCreate {
  request_id?: number | null;
  client_id: number;
  invoice_date: string;
  due_date: string;
  vat_rate: number;
  comment?: string;
  items: InvoiceItemCreate[];
  tax_system?: string;
  is_vat_included?: boolean;
}

export interface ActCreate {
  document_number?: string;
  request_id: number;
  client_id: number;
  total_amount: number;
  act_date: string;
  status?: ActStatus;
  comment?: string;
  // Добавьте эти поля:
  tax_system?: string;
  vat_rate?: number;
  is_vat_included?: boolean;
}

export interface Act {
  id: number;
  document_number: string;
  request_id: number | null;
  client_id: number | null;
  company_id: number | null;
  total_amount: string;
  act_date: string;
  status: ActStatus;
  signed_by_client_at: string | null;
  signed_by_executor_at: string | null;
  pdf_url: string | null;
  comment: string | null;
  created_at: string;
  updated_at: string;
  // Добавьте эти поля:
  tax_system?: string;
  vat_rate?: string;
  is_vat_included?: boolean;
}

export interface Payout {
  id: number;
  document_number: string;
  owner_id: number | null;
  vehicle_id: number | null;
  request_id: number | null;
  company_id: number | null;
  gross_amount: string;
  platform_commission: string;
  net_amount: string;
  commission_rate: string;
  payout_date: string;
  status: PayoutStatus;
  calculation_details: any;
  comment: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaymentCreate {
  invoice_id?: number;
  payout_id?: number;
  amount: number;
  method: PaymentMethod;
  payment_date: string;
  external_transaction_id?: string;
  comment?: string;
}

export interface Payment {
  id: number;
  invoice_id: number | null;
  payout_id: number | null;
  amount: string;
  method: string;
  payment_date: string;
  external_transaction_id: string | null;
  comment: string | null;
  created_at: string;
}

export interface PaymentsDashboard {
  total_revenue: string;
  total_paid: string;
  total_outstanding: string;
  total_commission_earned: string;
  invoices_count: number;
  acts_count: number;
  payouts_count: number;
}

// === PAYOUT BATCH (Sprint 4 Task 3) ===
export interface PayoutBatchRequest {
  date_from: string;
  date_to: string;
  commission_rate?: number;
}

export interface PayoutBatchResult {
  period_start: string;
  period_end: string;
  total_payouts: number;
  total_gross: number;
  total_commission: number;
  total_net: number;
  commission_rate: number;
  payouts: Array<{
    payout_id: number;
    document_number: string;
    owner_id: number;
    vehicle_id: number;
    vehicle_name: string;
    gross_amount: number;
    commission: number;
    net_amount: number;
    moto_hours: number;
    shifts_count: number;
  }>;
}

export interface PayoutsSummary {
  period_start: string;
  period_end: string;
  total_payouts: number;
  total_gross: number;
  total_commission: number;
  total_net: number;
  pending_payouts: number;
}

// === FINANCE DASHBOARD V2 (Sprint 4 Task 4) ===
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

export interface FinanceDashboardV2 {
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

export interface CompanyReview {
  id: number;
  company_id: number;
  reviewer_id: number | null;
  rating: number;
  comment: string | null;
  reviewer_name: string | null;
  reviewer_email: string | null;
  is_verified: number;
  is_published: number;
  moderation_status: string;
  created_at: string;
  updated_at: string;
}

export interface CompanyReviewListResponse {
  items: CompanyReview[];
  total: number;
  average_rating: number;
  rating_distribution: Record<number, number>;
}

export interface CompanyReviewCreate {
  rating: number;
  comment?: string;
  reviewer_name?: string;
  reviewer_email?: string;
}

export const reviewsApi = {
  async getCompanyReviews(companyId: number, limit = 20, offset = 0): Promise<CompanyReviewListResponse> {
    const response = await apiClient.get<CompanyReviewListResponse>(
      `/public/companies/${companyId}/reviews`,
      { params: { limit, offset } }
    );
    return response.data;
  },

  async createCompanyReview(companyId: number, data: CompanyReviewCreate): Promise<CompanyReview> {
    const response = await apiClient.post<CompanyReview>(
      `/public/companies/${companyId}/reviews`,
      data
    );
    return response.data;
  },

  async updateReview(reviewId: number, data: Partial<CompanyReviewCreate>): Promise<CompanyReview> {
    const response = await apiClient.patch<CompanyReview>(
      `/reviews/${reviewId}`,
      data
    );
    return response.data;
  },

  async deleteReview(reviewId: number): Promise<void> {
    await apiClient.delete(`/reviews/${reviewId}`);
  },
};

export const financeApi = {
  // === Invoices ===
  async getInvoices(params?: { status?: InvoiceStatus; limit?: number; offset?: number; contractor_id?: number; }): Promise<Invoice[]> {
    const response = await apiClient.get<Invoice[]>('/invoices', { params });
    return response.data;
  },

  async getInvoice(id: number): Promise<Invoice> {
    const response = await apiClient.get<Invoice>(`/invoices/${id}`);
    return response.data;
  },

  async createInvoice(data: InvoiceCreate): Promise<Invoice> {
    const payload = {
      request_id: data.request_id ?? 7,
      client_id: data.client_id,
      invoice_date: data.invoice_date,
      due_date: data.due_date,
      vat_rate: data.vat_rate,
      comment: data.comment || null,
      items: data.items.map((item) => ({
        description: item.description,
        quantity: item.quantity,
        unit_price: item.unit_price,
        amount: item.quantity * item.unit_price,
      })),
    };

    console.log('📤 Creating invoice:', payload);
    const response = await apiClient.post<Invoice>('/invoices', payload);
    return response.data;
  },

  async updateInvoice(id: number, data: Partial<InvoiceCreate>): Promise<Invoice> {
    const response = await apiClient.patch<Invoice>(`/invoices/${id}`, data);
    return response.data;
  },

  async deleteInvoice(id: number): Promise<void> {
    await apiClient.delete(`/invoices/${id}`);
  },

  async sendInvoice(id: number): Promise<Invoice> {
    const response = await apiClient.post<Invoice>(`/invoices/${id}/send`);
    return response.data;
  },

  downloadInvoicePdf: async (invoiceId: number): Promise<Blob> => {
    const response = await apiClient.get(`/invoices/${invoiceId}/pdf`, {
      responseType: 'blob',
    });
    return response.data;
  },

  /**
   * Скачать PDF акта
   */
  downloadActPdf: async (actId: number): Promise<Blob> => {
    const response = await apiClient.get(`/acts/${actId}/pdf`, {
      responseType: 'blob',
    });
    return response.data;
  },

  async downloadInvoiceFacturePdf(actId: number): Promise<Blob> {
    const response = await apiClient.get(`/acts/${actId}/invoice-facture`, {
      responseType: 'blob',
    });
    return response.data;
  },

  async downloadUpdPdf(actId: number): Promise<Blob> {
    const response = await apiClient.get(`/acts/${actId}/upd`, {
      responseType: 'blob',
    });
    return response.data;
  },

  async downloadTorg12Pdf(actId: number): Promise<Blob> {
    const response = await apiClient.get(`/acts/${actId}/torg12`, {
      responseType: 'blob',
    });
    return response.data;
  },

  // === Acts ===
  async getActs(params?: { status?: ActStatus; limit?: number; offset?: number; contractor_id?: number; }): Promise<Act[]> {
    const response = await apiClient.get<Act[]>('/acts', { params });
    return response.data;
  },

  async getAct(id: number): Promise<Act> {
    const response = await apiClient.get<Act>(`/acts/${id}`);
    return response.data;
  },

  async getContractorSummary(contractorId: number): Promise<{
    contractor_id: number;
    contractor_name: string;
    total_invoices: number;
    total_invoices_amount: number;
    paid_amount: number;
    unpaid_amount: number;
    payment_percentage: number;
    total_acts: number;
    total_acts_amount: number;
  }> {
    const response = await apiClient.get(`/finance/contractors/${contractorId}/summary`);
    return response.data;
  },

  async createAct(data: ActCreate): Promise<Act> {
    const response = await apiClient.post<Act>('/acts', data);
    return response.data;
  },

  async updateAct(id: number, data: Partial<ActCreate>): Promise<Act> {
    const response = await apiClient.patch<Act>(`/acts/${id}`, data);
    return response.data;
  },

  async deleteAct(id: number): Promise<void> {
    await apiClient.delete(`/acts/${id}`);
  },

  async signAct(id: number, signedBy: 'client' | 'executor'): Promise<Act> {
    const response = await apiClient.post<Act>(`/acts/${id}/sign`, {
      signed_by: signedBy,
    });
    return response.data;
  },

  async getPayouts(params?: any): Promise<Payout[]> {
    const response = await apiClient.get('/finance/payouts', { params });
    return response.data;
  }

  // === Payments ===
  async createPayment(data: PaymentCreate): Promise<Payment> {
    const response = await apiClient.post<Payment>('/payments', data);
    return response.data;
  },

  async getPayments(params?: { limit?: number; offset?: number }): Promise<Payment[]> {
    const response = await apiClient.get<Payment[]>('/payments', { params });
    return response.data;
  },

  // === Dashboard ===
  async getDashboard(): Promise<PaymentsDashboard> {
    const response = await apiClient.get<PaymentsDashboard>('/payments/dashboard');
    return response.data;
  },

  // 🆕 НОВАЯ ФУНКЦИЯ: Отправить счёт повторно (с PDF вложением)
  async resendInvoiceEmail(id: number): Promise<Invoice> {
    const response = await apiClient.post<Invoice>(`/invoices/${id}/resend-email`);
    return response.data;
  },

  // 🆕 НОВАЯ ФУНКЦИЯ: Отправить акт повторно (с PDF вложением)
  async resendActEmail(id: number): Promise<Act> {
    const response = await apiClient.post<Act>(`/acts/${id}/resend-email`);
    return response.data;
  },

  calculatePayoutsBatch: async (data: PayoutBatchRequest): Promise<PayoutBatchResult> => {
    // 🆕 ИСПРАВЛЕНО: используем payouts router
    const response = await apiClient.post('/finance/payouts/calculate', null, { 
      params: data 
    });
    return response.data;
  },

  approvePayout: async (id: number): Promise<Payout> => {
    const response = await apiClient.post(`/finance/payouts/${id}/approve`);
    return response.data;
  },

  payPayout: async (id: number): Promise<Payout> => {
    const response = await apiClient.post(`/finance/payouts/${id}/pay`);
    return response.data;
  },

  getPayoutsSummary: async (dateFrom: string, dateTo: string): Promise<PayoutsSummary> => {
    const params = new URLSearchParams({
      date_from: dateFrom,
      date_to: dateTo,
    });
    const response = await apiClient.get(`/finance/payouts/summary?${params}`);
    return response.data;
  },

  // === FINANCE DASHBOARD V2 (Sprint 4 Task 4) ===
  getFinanceDashboardV2: async (dateFrom: string, dateTo: string): Promise<FinanceDashboardV2> => {
    const params = new URLSearchParams({
      date_from: dateFrom,
      date_to: dateTo,
    });
    const response = await apiClient.get(`/finance/dashboard?${params}`);
    return response.data;
  },

  getRevenueByClient: async (dateFrom: string, dateTo: string, limit: number = 10): Promise<ClientRevenue[]> => {
    const params = new URLSearchParams({
      date_from: dateFrom,
      date_to: dateTo,
      limit: limit.toString(),
    });
    const response = await apiClient.get(`/finance/revenue-by-client?${params}`);
    return response.data.clients || [];
  },

  getRevenueByVehicle: async (dateFrom: string, dateTo: string, limit: number = 10): Promise<VehicleRevenue[]> => {
    const params = new URLSearchParams({
      date_from: dateFrom,
      date_to: dateTo,
      limit: limit.toString(),
    });
    const response = await apiClient.get(`/finance/revenue-by-vehicle?${params}`);
    return response.data.vehicles || [];
  },
};
