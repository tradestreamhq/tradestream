import axios from 'axios';

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  withCredentials: true, // For httpOnly refresh token cookie
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor will be added by the useAuth hook to inject tokens
// Response interceptor will be added by the useAuth hook to handle token refresh
