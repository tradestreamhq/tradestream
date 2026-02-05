import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { authApi } from '@/api/auth';
import { api } from '@/api/client';
import type { User } from '@/types';
import type { AxiosError, InternalAxiosRequestConfig } from 'axios';

interface AuthState {
  user: User | null;
  accessToken: string | null;
  isDemo: boolean;
  isLoading: boolean;

  // Actions
  login: (email: string, password: string) => Promise<void>;
  loginWithOAuth: (provider: string) => void;
  loginAsDemo: () => Promise<void>;
  register: (email: string, password: string, displayName: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshToken: () => Promise<void>;
  setAccessToken: (token: string, user?: User) => void;
}

export const useAuth = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      isDemo: false,
      isLoading: false,

      login: async (email, password) => {
        set({ isLoading: true });
        try {
          const response = await authApi.login(email, password);
          set({
            user: response.user,
            accessToken: response.access_token,
            isDemo: false,
          });
        } finally {
          set({ isLoading: false });
        }
      },

      loginWithOAuth: (provider) => {
        const apiUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
        window.location.href = `${apiUrl}/auth/oauth/${provider}`;
      },

      loginAsDemo: async () => {
        set({ isLoading: true });
        try {
          const response = await authApi.demo();
          set({
            user: null,
            accessToken: response.access_token,
            isDemo: true,
          });
        } finally {
          set({ isLoading: false });
        }
      },

      register: async (email, password, displayName) => {
        set({ isLoading: true });
        try {
          await authApi.register(email, password, displayName);
          // Don't auto-login, require email verification
        } finally {
          set({ isLoading: false });
        }
      },

      logout: async () => {
        try {
          await authApi.logout();
        } catch {
          // Ignore errors, clear local state anyway
        }
        set({ user: null, accessToken: null, isDemo: false });
      },

      refreshToken: async () => {
        try {
          const response = await authApi.refresh();
          set({ accessToken: response.access_token });
        } catch {
          // Refresh failed, logout
          get().logout();
        }
      },

      setAccessToken: (token, user) => {
        set({ accessToken: token, user: user ?? null, isDemo: false });
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        accessToken: state.accessToken,
        user: state.user,
        isDemo: state.isDemo,
      }),
    }
  )
);

// Setup axios interceptors after the store is created
// Request interceptor - add auth token
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = useAuth.getState().accessToken;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor - handle token refresh
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && originalRequest && !('_retry' in originalRequest)) {
      // Mark request as retried to prevent infinite loops
      (originalRequest as InternalAxiosRequestConfig & { _retry?: boolean })._retry = true;

      // Try to refresh token
      try {
        await useAuth.getState().refreshToken();
        // Retry original request with new token
        return api(originalRequest);
      } catch {
        // Refresh failed, redirect to login
        useAuth.getState().logout();
        if (typeof window !== 'undefined') {
          window.location.href = '/login';
        }
      }
    }

    return Promise.reject(error);
  }
);
