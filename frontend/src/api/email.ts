import apiClient from './client';

export interface EmailLog {
  id: number;
  to_email: string;
  to_name?: string | null;
  subject: string;
  status: 'pending' | 'sent' | 'delivered' | 'failed' | 'bounced';
  error_message?: string | null;
  sent_at?: string | null;
  invoice_id?: number | null;
  act_id?: number | null;
  created_at: string;
}

export interface EmailLogsResponse {
  items: EmailLog[];
  total: number;
  limit: number;
  offset: number;
}

export const emailApi = {
  async getLogs(params?: {
    limit?: number;
    offset?: number;
    status?: string;
  }): Promise<EmailLogsResponse> {
    const response = await apiClient.get<EmailLogsResponse>('/email/logs', {
      params,
    });
    return response.data;
  },

  async getLogDetail(logId: number): Promise<EmailLog & { html_body?: string; text_body?: string }> {
    const response = await apiClient.get(`/email/logs/${logId}`);
    return response.data;
  },

  async deleteLog(logId: number): Promise<void> {
    await apiClient.delete(`/email/logs/${logId}`);
  },
};
