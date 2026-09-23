import apiClient from './client';

export type EmailTemplateType =
  | 'invoice_created'
  | 'invoice_overdue'
  | 'act_created'
  | 'act_signed'
  | 'maintenance_completed'
  | 'welcome'
  | 'custom';

export type EmailStatus = 'pending' | 'sent' | 'delivered' | 'failed' | 'bounced';

export interface EmailTemplate {
  id: number;
  company_id: number;
  name: string;
  template_type: EmailTemplateType;
  subject: string;
  html_body: string;
  text_body?: string;
  description?: string;
  is_active: boolean;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface EmailTemplateCreate {
  name: string;
  template_type: EmailTemplateType;
  subject: string;
  html_body: string;
  text_body?: string;
  description?: string;
  is_active?: boolean;
  is_default?: boolean;
}

export interface EmailTemplateUpdate {
  name?: string;
  subject?: string;
  html_body?: string;
  text_body?: string;
  description?: string;
  is_active?: boolean;
  is_default?: boolean;
}

export interface EmailLog {
  id: number;
  company_id: number;
  template_id?: number;
  to_email: string;
  to_name?: string;
  subject: string;
  html_body?: string;
  text_body?: string;
  status: EmailStatus;
  error_message?: string;
  invoice_id?: number;
  act_id?: number;
  maintenance_order_id?: number;
  sent_at?: string;
  delivered_at?: string;
  created_at: string;
}

export interface BulkSendRequest {
  template_id: number;
  recipient_emails: string[];
  context: Record<string, any>;
}

export interface BulkSendResult {
  total: number;
  sent: number;
  failed: number;
  results: Array<{
    email: string;
    status: string;
    error?: string;
  }>;
}

export async function getEmailTemplates(params?: {
  skip?: number;
  limit?: number;
  template_type?: EmailTemplateType;
  is_active?: boolean;
}): Promise<EmailTemplate[]> {
  const searchParams = new URLSearchParams();
  if (params?.skip) searchParams.set('skip', params.skip.toString());
  if (params?.limit) searchParams.set('limit', params.limit.toString());
  if (params?.template_type) searchParams.set('template_type', params.template_type);
  if (params?.is_active !== undefined) searchParams.set('is_active', params.is_active.toString());

  const response = await apiClient.get(`/email-templates/?${searchParams}`);
  return response.data;
}

export async function getEmailTemplate(templateId: number): Promise<EmailTemplate> {
  const response = await apiClient.get(`/email-templates/${templateId}`);
  return response.data;
}

export async function createEmailTemplate(data: EmailTemplateCreate): Promise<EmailTemplate> {
  const response = await apiClient.post('/email-templates/', data);
  return response.data;
}

export async function updateEmailTemplate(
  templateId: number,
  data: EmailTemplateUpdate
): Promise<EmailTemplate> {
  const response = await apiClient.put(`/email-templates/${templateId}`, data);
  return response.data;
}

export async function deleteEmailTemplate(templateId: number): Promise<void> {
  await apiClient.delete(`/email-templates/${templateId}`);
}

export async function bulkSendEmails(data: BulkSendRequest): Promise<BulkSendResult> {
  const response = await apiClient.post('/email-bulk/send', data);
  return response.data;
}

export async function getEmailLogs(params?: {
  skip?: number;
  limit?: number;
  status?: EmailStatus;
  template_id?: number;
}): Promise<EmailLog[]> {
  const searchParams = new URLSearchParams();
  if (params?.skip) searchParams.set('skip', params.skip.toString());
  if (params?.limit) searchParams.set('limit', params.limit.toString());
  if (params?.status) searchParams.set('status', params.status);
  if (params?.template_id) searchParams.set('template_id', params.template_id.toString());

  const response = await apiClient.get(`/email-bulk/logs?${searchParams}`);
  return response.data;
}
