import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export const loginApi = async (email: string, password: string): Promise<AuthResponse> => {
  const response = await axios.post<AuthResponse>(
    `${API_URL}/auth/login`,
    {
      email: email,
      password: password
    },
    {
      headers: { 'Content-Type': 'application/json' }
    }
  );
  return response.data;
};
