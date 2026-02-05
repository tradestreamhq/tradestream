// User types (matches backend API contract with snake_case)
export interface User {
  user_id: string;
  email: string;
  display_name: string;
  avatar_url: string | null;
  is_provider: boolean;
  email_verified: boolean;
}

// Auth types
export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  display_name: string;
}

export interface AuthResponse {
  user: User;
  access_token: string;
  refresh_token?: string;
  expires_in?: number;
}

export interface RefreshResponse {
  access_token: string;
  expires_in?: number;
}

// API Error types
export interface ApiError {
  message: string;
  code?: string;
  details?: Record<string, unknown>;
}
