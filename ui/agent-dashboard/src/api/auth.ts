import { api } from './client';
import type { LoginRequest, RegisterRequest, AuthResponse, RefreshResponse } from '@/types';

export const authApi = {
  /**
   * Login with email and password
   */
  login: async (email: string, password: string): Promise<AuthResponse> => {
    const response = await api.post<AuthResponse>('/auth/login', {
      email,
      password,
    } satisfies LoginRequest);
    return response.data;
  },

  /**
   * Register a new user
   */
  register: async (
    email: string,
    password: string,
    displayName: string
  ): Promise<void> => {
    await api.post('/auth/register', {
      email,
      password,
      display_name: displayName,
    } satisfies RegisterRequest);
  },

  /**
   * Login as demo user (anonymous access)
   */
  demo: async (): Promise<{ access_token: string }> => {
    const response = await api.post<{ access_token: string }>('/auth/demo');
    return response.data;
  },

  /**
   * Logout (invalidates refresh token)
   */
  logout: async (): Promise<void> => {
    await api.post('/auth/logout');
  },

  /**
   * Refresh access token using httpOnly refresh token cookie
   */
  refresh: async (): Promise<RefreshResponse> => {
    const response = await api.post<RefreshResponse>('/auth/refresh');
    return response.data;
  },

  /**
   * Verify email with token
   */
  verifyEmail: async (token: string): Promise<void> => {
    await api.post('/auth/verify-email', { token });
  },

  /**
   * Request password reset
   */
  forgotPassword: async (email: string): Promise<void> => {
    await api.post('/auth/forgot-password', { email });
  },

  /**
   * Reset password with token
   */
  resetPassword: async (token: string, newPassword: string): Promise<void> => {
    await api.post('/auth/reset-password', { token, new_password: newPassword });
  },
};
