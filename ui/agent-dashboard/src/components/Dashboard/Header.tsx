import { Bell, User, LogOut, Settings } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { Button } from '@/components/ui/button';
import { useNavigate } from 'react-router';
import { useState } from 'react';

export function Header() {
  const { user, isDemo, logout } = useAuth();
  const navigate = useNavigate();
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [isConnected] = useState(true); // TODO: Connect to SSE status

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b border-slate-700 bg-slate-900/95 backdrop-blur supports-[backdrop-filter]:bg-slate-900/80">
      <div className="flex h-16 items-center justify-between px-4 lg:px-6">
        {/* Logo */}
        <div className="flex items-center gap-2">
          <a href="/" className="flex items-center gap-2 text-xl font-bold text-white hover:text-blue-400 transition-colors">
            <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-cyan-400 rounded-lg flex items-center justify-center">
              <span className="text-white text-sm font-bold">TS</span>
            </div>
            <span className="hidden sm:inline">TradeStream</span>
          </a>
        </div>

        {/* Right side: Connection Status, Notifications, User Menu */}
        <div className="flex items-center gap-4">
          {/* Connection Status */}
          <div className="flex items-center gap-2 text-sm">
            <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'} animate-pulse`} />
            <span className="hidden md:inline text-slate-400">
              {isConnected ? 'Connected' : 'Disconnected'}
            </span>
          </div>

          {/* Notifications - only for authenticated users */}
          {user && !isDemo && (
            <Button
              variant="ghost"
              size="icon"
              className="relative text-slate-400 hover:text-white"
            >
              <Bell className="h-5 w-5" />
              <span className="absolute top-1 right-1 w-2 h-2 bg-blue-500 rounded-full" />
            </Button>
          )}

          {/* User Menu */}
          {user || isDemo ? (
            <div className="relative">
              <Button
                variant="ghost"
                size="icon"
                className="text-slate-400 hover:text-white"
                onClick={() => setShowUserMenu(!showUserMenu)}
              >
                {user?.avatar_url ? (
                  <img
                    src={user.avatar_url}
                    alt={user.display_name}
                    className="w-8 h-8 rounded-full"
                  />
                ) : (
                  <User className="h-5 w-5" />
                )}
              </Button>

              {/* Dropdown Menu */}
              {showUserMenu && (
                <>
                  {/* Backdrop */}
                  <div
                    className="fixed inset-0 z-40"
                    onClick={() => setShowUserMenu(false)}
                  />

                  {/* Menu */}
                  <div className="absolute right-0 mt-2 w-56 bg-slate-800 border border-slate-700 rounded-lg shadow-lg z-50 overflow-hidden">
                    {/* User Info */}
                    <div className="px-4 py-3 border-b border-slate-700">
                      <p className="text-sm font-medium text-white">
                        {isDemo ? 'Demo User' : user?.display_name}
                      </p>
                      <p className="text-xs text-slate-400 truncate">
                        {isDemo ? 'demo@tradestream.ai' : user?.email}
                      </p>
                    </div>

                    {/* Menu Items */}
                    <div className="py-1">
                      {!isDemo && (
                        <>
                          <button
                            className="w-full px-4 py-2 text-sm text-left text-slate-300 hover:bg-slate-700 flex items-center gap-2"
                            onClick={() => {
                              setShowUserMenu(false);
                              navigate('/settings');
                            }}
                          >
                            <Settings className="h-4 w-4" />
                            Settings
                          </button>
                        </>
                      )}
                      <button
                        className="w-full px-4 py-2 text-sm text-left text-red-400 hover:bg-slate-700 flex items-center gap-2"
                        onClick={handleLogout}
                      >
                        <LogOut className="h-4 w-4" />
                        {isDemo ? 'Exit Demo' : 'Logout'}
                      </button>
                    </div>
                  </div>
                </>
              )}
            </div>
          ) : (
            <Button
              onClick={() => navigate('/login')}
              className="bg-gradient-to-r from-blue-500 to-cyan-400 hover:from-blue-600 hover:to-cyan-500 text-white"
            >
              Sign In
            </Button>
          )}
        </div>
      </div>
    </header>
  );
}
