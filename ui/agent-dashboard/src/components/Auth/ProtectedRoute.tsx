import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';

interface ProtectedRouteProps {
  children: React.ReactNode;
  allowDemo?: boolean;
}

export function ProtectedRoute({
  children,
  allowDemo = true,
}: ProtectedRouteProps) {
  const { accessToken, isDemo } = useAuth();
  const location = useLocation();

  if (!accessToken) {
    // Redirect to login, preserving the intended destination
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (isDemo && !allowDemo) {
    // Demo users trying to access auth-only features
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}
