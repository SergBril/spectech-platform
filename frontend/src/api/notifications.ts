import apiClient from './client';

export interface Notification {
  id: number;
  user_id: number;
  alert_id?: number;
  channel: string;
  title: string;
  body: string;
  is_read: boolean;
  read_at?: string;
  sent_at: string;
}

export const notificationsApi = {
  async getUnreadCount(): Promise<{ count: number }> {
    const response = await apiClient.get<{ count: number }>('/telematics/notifications/unread-count');
    return response.data;
  },

  async getAll(unreadOnly = false, limit = 50): Promise<Notification[]> {
    const response = await apiClient.get<Notification[]>('/telematics/notifications', {
      params: { unread_only: unreadOnly, limit },
    });
    return response.data;
  },

  async markRead(notificationId: number): Promise<void> {
    await apiClient.post(`/telematics/notifications/${notificationId}/read`);
  },

  async markAllRead(): Promise<{ updated: number }> {
    const response = await apiClient.post<{ updated: number }>('/telematics/notifications/mark-all-read');
    return response.data;
  },
};
