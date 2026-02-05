import { useAuth } from '@/hooks/useAuth';

export function Dashboard() {
  const { user, isDemo } = useAuth();

  return (
    <div className="min-h-screen bg-slate-900 p-8">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-3xl font-bold text-white mb-4">
          Dashboard
        </h1>

        {isDemo && (
          <div className="mb-4 p-4 bg-amber-500/10 border border-amber-500/20 rounded-lg text-amber-500">
            You're in demo mode.{' '}
            <a href="/register" className="underline font-medium">
              Sign up
            </a>{' '}
            to save your settings and unlock all features.
          </div>
        )}

        {user && (
          <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
            <h2 className="text-xl font-semibold text-white mb-2">
              Welcome, {user.display_name}!
            </h2>
            <p className="text-slate-400">
              Email: {user.email}
            </p>
            <p className="text-slate-400">
              Email Verified: {user.email_verified ? 'Yes' : 'No'}
            </p>
            <p className="text-slate-400">
              Provider Status: {user.is_provider ? 'Active' : 'Not a provider'}
            </p>
          </div>
        )}

        {isDemo && !user && (
          <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
            <h2 className="text-xl font-semibold text-white mb-2">
              Demo Mode
            </h2>
            <p className="text-slate-400">
              You're viewing the dashboard in demo mode. Sign up to access all features.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
