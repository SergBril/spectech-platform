import apiClient from './client';

export type InvoiceStatus = 'draft' | 'sent' | 'paid' | 'partially_paid' | 'overdue' | 'cancelled';
export type ActStatus = 'draft' | 'sent' | 'paid' | 'overdue' | 'cancelled';
export type PayoutStatus = 'draft' | 'sent' | 'paid' | 'overdue' | 'cancelled';

export interface InvoiceItem {
  id?: number;
  description: string;
  quantity: number;
  unit_price: number;
  amount: number;
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

export interface Act {
  id: number;
  document_number: string;
  request_id: number | null;
  client_id: number | null;
  company_id: number | null;
  total_amount: string;  // ← ПРАВИЛЬНОЕ имя поля (НЕ total)
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
  owner_id: number | null;  // ← НЕ contractor_id!
  vehicle_id: number | null;
  request_id: number | null;
  company_id: number | null;
  gross_amount: string;  // валовая сумма
  platform_commission: string;  // комиссия платформы
  net_amount: string;  // сумма к выплате
  commission_rate: string;
  payout_date: string;
  status: PayoutStatus;
  calculation_details: any;
  comment: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaymentsDashboard {
  total_revenue: string;          // Общий доход
  total_paid: string;             // Оплачено
  total_outstanding: string;      // К получению (задолженность)
  total_commission_earned: string; // Заработанная комиссия
  invoices_count: number;         // Количество счетов
  acts_count: number;             // Количество актов
  payouts_count: number;          // Количество выплат
}

export const financeApi = {
  // Invoices
  async getInvoices(params?: { status?: InvoiceStatus; limit?: number; offset?: number }): Promise<Invoice[]> {
    const response = await apiClient.get<Invoice[]>('/invoices', { params });
    return response.data;
  },

  async getInvoice(id: number): Promise<Invoice> {
    const response = await apiClient.get<Invoice>(`/invoices/${id}`);
    return response.data;
  },

  // Acts
  async getActs(params?: { status?: ActStatus; limit?: number; offset?: number }): Promise<Act[]> {
    const response = await apiClient.get<Act[]>('/acts', { params });
    return response.data;
  },

  // Payouts
  async getPayouts(params?: { status?: PayoutStatus; limit?: number; offset?: number }): Promise<Payout[]> {
    const response = await apiClient.get<Payout[]>('/payouts', { params });
    return response.data;
  },

  // Dashboard
  async getDashboard(): Promise<PaymentsDashboard> {
    const response = await apiClient.get<PaymentsDashboard>('/payments/dashboard');
    return response.data;
  },
};
