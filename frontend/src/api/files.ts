import apiClient from './client';

export interface UploadedFile {
  id: number;
  original_filename: string;
  storage_path: string;
  content_type: string;
  size_bytes: number;
  file_category: string;
  vehicle_id?: number | null;
  invoice_id?: number | null;
  act_id?: number | null;
  contractor_id?: number | null;
  uploaded_by?: number | null;
  created_at: string;
  url?: string;
  presigned_url?: string;
}

export interface FileUploadResponse {
  id: number;
  original_filename: string;
  storage_path: string;
  content_type: string;
  size_bytes: number;
  url: string;
  presigned_url: string;
}

export const filesApi = {
  /**
   * Загрузить файл в MinIO
   */
  upload: async (
    file: File,
    fileCategory: string,
    options?: {
      vehicle_id?: number;
      invoice_id?: number;
      act_id?: number;
      contractor_id?: number;
    },
    onProgress?: (percent: number) => void
  ): Promise<FileUploadResponse> => {
    const formData = new FormData();
    formData.append('file', file);

    // Формируем query-параметры
    const params = new URLSearchParams();
    params.append('file_category', fileCategory);
    if (options?.vehicle_id) params.append('vehicle_id', String(options.vehicle_id));
    if (options?.invoice_id) params.append('invoice_id', String(options.invoice_id));
    if (options?.act_id) params.append('act_id', String(options.act_id));
    if (options?.contractor_id) params.append('contractor_id', String(options.contractor_id));

    const response = await apiClient.post(`/files/upload?${params.toString()}`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total && onProgress) {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onProgress(percent);
        }
      },
    });

    return response.data;
  },

  /**
   * Получить список файлов с фильтрами
   */
  list: async (filters?: {
    file_category?: string;
    vehicle_id?: number;
    invoice_id?: number;
    limit?: number;
  }): Promise<UploadedFile[]> => {
    const params = new URLSearchParams();
    if (filters?.file_category) params.append('file_category', filters.file_category);
    if (filters?.vehicle_id) params.append('vehicle_id', String(filters.vehicle_id));
    if (filters?.invoice_id) params.append('invoice_id', String(filters.invoice_id));
    if (filters?.limit) params.append('limit', String(filters.limit));

    const query = params.toString() ? `?${params.toString()}` : '';
    const response = await apiClient.get(`/files/${query}`);
    return response.data;
  },

  /**
   * Получить presigned URL для скачивания
   */
  getDownloadUrl: async (fileId: number, expiresIn: number = 3600): Promise<string> => {
    const response = await apiClient.get(`/files/presigned-url/${fileId}?expires_in=${expiresIn}`);
    return response.data.presigned_url;
  },

  /**
   * Скачать файл напрямую (через backend proxy)
   */
  download: async (fileId: number, filename: string): Promise<void> => {
    const response = await apiClient.get(`/files/download/${fileId}`, {
      responseType: 'blob',
    });

    const blob = new Blob([response.data]);
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  },

  /**
   * Удалить файл
   */
  delete: async (fileId: number): Promise<void> => {
    await apiClient.delete(`/files/${fileId}`);
  },

  /**
   * Статистика хранилища
   */
  stats: async () => {
    const response = await apiClient.get('/files/stats');
    return response.data;
  },
};
