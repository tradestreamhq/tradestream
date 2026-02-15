import { useAuth } from '@/hooks/useAuth';

export function Dashboard() {
  const { user, isDemo } = useAuth();

  return (
    <div className="max-w-7xl mx-auto">
      <h1 className="text-3xl font-bold text-white mb-6">
        Dashboard
      </h1>

      {user && (
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
          <h2 className="text-xl font-semibold text-white mb-4">
            Welcome, {user.display_name}!
          </h2>
          <div className="space-y-2 text-slate-400">
            <p>
              <span className="font-medium text-slate-300">Email:</span> {user.email}
            </p>
            <p>
              <span className="font-medium text-slate-300">Email Verified:</span>{' '}
              {user.email_verified ? (
                <span className="text-green-400">Yes</span>
              ) : (
                <span className="text-amber-400">No</span>
              )}
            </p>
            <p>
              <span className="font-medium text-slate-300">Provider Status:</span>{' '}
              {user.is_provider ? (
                <span className="text-blue-400">Active</span>
              ) : (
                <span className="text-slate-400">Not a provider</span>
              )}
            </p>
          </div>
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
  );
}
