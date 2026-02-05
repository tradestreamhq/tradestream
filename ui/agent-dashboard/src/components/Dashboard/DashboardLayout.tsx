import { Outlet } from 'react-router';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { useAuth } from '@/hooks/useAuth';

export function DashboardLayout() {
  const { isDemo } = useAuth();

  return (
    <div className="min-h-screen bg-slate-900">
      <Header />

      <div className="flex">
        <Sidebar />

        <main className="flex-1 min-h-[calc(100vh-4rem)]">
          {/* Demo Banner */}
          {isDemo && (
            <div className="sticky top-16 z-30 bg-amber-500/10 border-b border-amber-500/20 px-4 py-3">
              <div className="max-w-7xl mx-auto text-center">
                <span className="text-amber-500 text-sm font-medium">
                  You're in demo mode.{' '}
                  <a href="/register" className="underline font-semibold hover:text-amber-400">
                    Sign up
                  </a>{' '}
                  to save your settings and unlock all features.
                </span>
              </div>
            </div>
          )}

          {/* Content Area */}
          <div className="p-4 lg:p-6">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
