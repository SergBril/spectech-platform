import apiClient from './client';

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export const loginApi = async (email: string, password: string): Promise<AuthResponse> => {
  const response = await apiClient.post<AuthResponse>(
    '/auth/login',
    {
      email: email,
      password: password,
    }
  );
  return response.data;
};

export const refreshApi = async (refreshToken: string): Promise<AuthResponse> => {
  const response = await apiClient.post<AuthResponse>('/auth/refresh', {
    refresh_token: refreshToken,
  });
  return response.data;
};
