import apiClient from './client';

export interface ExportFilters {
  status?: string;
  date_from?: string;
  date_to?: string;
}

export const exportApi = {
  async invoicesCsv(filters: ExportFilters = {}): Promise<Blob> {
    const response = await apiClient.get('/export/invoices/csv', {
      params: filters,
      responseType: 'blob',
    });
    return response.data;
  },

  async actsCsv(filters: ExportFilters = {}): Promise<Blob> {
    const response = await apiClient.get('/export/acts/csv', {
      params: filters,
      responseType: 'blob',
    });
    return response.data;
  },

  async requestReport(requestId: number): Promise<Blob> {
    const response = await apiClient.get(`/export/requests/${requestId}/report`, {
      responseType: 'blob',
    });
    return response.data;
  },
};

export const downloadBlob = (blob: Blob, filename: string) => {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};
