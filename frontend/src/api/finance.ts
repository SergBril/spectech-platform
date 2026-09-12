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
}

export interface InvoiceCreate {
  request_id?: number | null;
  client_id: number;
  invoice_date: string;
  due_date: string;
  vat_rate: number;
  comment?: string;
  items: InvoiceItemCreate[];
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

export const financeApi = {
  // === Invoices ===
  async getInvoices(params?: { status?: InvoiceStatus; limit?: number; offset?: number }): Promise<Invoice[]> {
    const response = await apiClient.get<Invoice[]>('/invoices', { params });
    return response.data;
  },

  async getInvoice(id: number): Promise<Invoice> {
    const response = await apiClient.get<Invoice>(`/invoices/${id}`);
    return response.data;
  },

  async createInvoice(data: InvoiceCreate): Promise<Invoice> {
    const payload = {
      request_id: data.request_id ?? 7,  // ← По умолчанию заявка #7 (Земляные работы)
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

  async downloadInvoicePdf(id: number): Promise<Blob> {
    const response = await apiClient.get(`/invoices/${id}/pdf`, {
      responseType: 'blob',
    });
    return response.data;
  },

  // === Acts ===
  async getActs(params?: { status?: ActStatus; limit?: number; offset?: number }): Promise<Act[]> {
    const response = await apiClient.get<Act[]>('/acts', { params });
    return response.data;
  },

  // === Payouts ===
  async getPayouts(params?: { status?: PayoutStatus; limit?: number; offset?: number }): Promise<Payout[]> {
    const response = await apiClient.get<Payout[]>('/payouts', { params });
    return response.data;
  },

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
};
