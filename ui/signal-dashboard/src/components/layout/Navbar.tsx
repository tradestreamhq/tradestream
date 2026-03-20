import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { cn } from "@/utils/utils";

const NAV_LINKS = [
  { to: "/signals", label: "Signals" },
  { to: "/strategies", label: "Strategies" },
  { to: "/builder", label: "Builder" },
  { to: "/marketplace", label: "Marketplace" },
  { to: "/history", label: "History" },
];

export function Navbar() {
  const { isAuthenticated, logout, user } = useAuth();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <nav className="border-b border-slate-700/50 bg-surface">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
        <Link to="/" className="text-xl font-bold text-cyan-400">
          TradeStream
        </Link>

        {/* Desktop nav */}
        <div className="hidden items-center gap-6 md:flex">
          {isAuthenticated &&
            NAV_LINKS.map((link) => (
              <Link
                key={link.to}
                to={link.to}
                className={cn(
                  "text-sm font-medium transition-colors hover:text-white",
                  location.pathname === link.to
                    ? "text-white"
                    : "text-slate-400"
                )}
              >
                {link.label}
              </Link>
            ))}

          {isAuthenticated ? (
            <div className="flex items-center gap-4">
              <Link
                to="/account"
                className="text-sm font-medium text-slate-400 transition-colors hover:text-white"
              >
                {user?.name || "Account"}
              </Link>
              <button
                onClick={logout}
                className="text-sm font-medium text-slate-500 transition-colors hover:text-red-400"
              >
                Sign Out
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-3">
              <Link to="/login" className="btn-secondary text-sm">
                Sign In
              </Link>
              <Link to="/register" className="btn-primary text-sm">
                Get Started
              </Link>
            </div>
          )}
        </div>

        {/* Mobile hamburger */}
        <button
          className="md:hidden text-slate-400"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label="Toggle navigation menu"
          aria-expanded={mobileOpen}
        >
          <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            {mobileOpen ? (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            ) : (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            )}
          </svg>
        </button>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <div className="border-t border-slate-700/50 px-4 py-4 md:hidden">
          <div className="flex flex-col gap-3">
            {isAuthenticated &&
              NAV_LINKS.map((link) => (
                <Link
                  key={link.to}
                  to={link.to}
                  onClick={() => setMobileOpen(false)}
                  className={cn(
                    "rounded-lg px-3 py-2 text-sm font-medium",
                    location.pathname === link.to
                      ? "bg-surface-card text-white"
                      : "text-slate-400"
                  )}
                >
                  {link.label}
                </Link>
              ))}
            {isAuthenticated ? (
              <>
                <Link
                  to="/account"
                  onClick={() => setMobileOpen(false)}
                  className="rounded-lg px-3 py-2 text-sm font-medium text-slate-400"
                >
                  Account
                </Link>
                <button
                  onClick={() => {
                    logout();
                    setMobileOpen(false);
                  }}
                  className="rounded-lg px-3 py-2 text-left text-sm font-medium text-red-400"
                >
                  Sign Out
                </button>
              </>
            ) : (
              <>
                <Link
                  to="/login"
                  onClick={() => setMobileOpen(false)}
                  className="rounded-lg px-3 py-2 text-sm font-medium text-slate-400"
                >
                  Sign In
                </Link>
                <Link
                  to="/register"
                  onClick={() => setMobileOpen(false)}
                  className="btn-primary text-center text-sm"
                >
                  Get Started
                </Link>
              </>
            )}
          </div>
        </div>
      )}
    </nav>
  );
}
