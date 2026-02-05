// User types
export interface User {
  id: string;
  email: string;
  username?: string;
  role: 'user' | 'provider' | 'admin';
  emailVerified: boolean;
  createdAt: string;
  updatedAt: string;
}

// Auth types
export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  username?: string;
}

export interface AuthResponse {
  user: User;
  tokens: AuthTokens;
}

// API Error types
export interface ApiError {
  message: string;
  code?: string;
  details?: Record<string, unknown>;
}
