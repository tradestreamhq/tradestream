import { Home, Activity, Trophy, Award, Gift, Menu, X } from 'lucide-react';
import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router';
import { Button } from '@/components/ui/button';

interface NavItem {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  path: string;
}

const navItems: NavItem[] = [
  { icon: Home, label: 'Home', path: '/dashboard' },
  { icon: Activity, label: 'Feed', path: '/feed' },
  { icon: Trophy, label: 'Leaderboards', path: '/leaderboards' },
  { icon: Award, label: 'Achievements', path: '/achievements' },
  { icon: Gift, label: 'Referrals', path: '/referrals' },
];

export function Sidebar() {
  const [isOpen, setIsOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();

  const isActive = (path: string) => location.pathname === path;

  return (
    <>
      {/* Mobile Menu Button */}
      <Button
        variant="ghost"
        size="icon"
        className="fixed bottom-4 right-4 z-50 lg:hidden bg-slate-800 hover:bg-slate-700 text-white shadow-lg"
        onClick={() => setIsOpen(!isOpen)}
      >
        {isOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
      </Button>

      {/* Mobile Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setIsOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed lg:sticky top-16 left-0 h-[calc(100vh-4rem)] w-64
          bg-slate-900 border-r border-slate-700
          transform transition-transform duration-200 ease-in-out z-40
          ${isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        `}
      >
        <nav className="flex flex-col gap-1 p-4">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.path);

            return (
              <button
                key={item.path}
                onClick={() => {
                  navigate(item.path);
                  setIsOpen(false);
                }}
                className={`
                  flex items-center gap-3 px-4 py-3 rounded-lg
                  text-sm font-medium transition-colors
                  ${
                    active
                      ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                      : 'text-slate-400 hover:text-white hover:bg-slate-800'
                  }
                `}
              >
                <Icon className="h-5 w-5" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </aside>
    </>
  );
}
