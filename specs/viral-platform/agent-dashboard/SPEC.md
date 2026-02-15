# Agent Dashboard Frontend Specification

## Goal

Build a modern React frontend for the viral trading signal platform with landing page, authentication flows, real-time signal dashboard, and social features.

## Target Behavior

The agent-dashboard is a single-page application that provides:
- Public landing page with value proposition
- Auth flows (email, OAuth, demo mode)
- Real-time signal streaming dashboard
- Provider profiles and social features
- Settings and personalization
- Gamification displays (streaks, achievements)

## Technology Stack

| Technology | Purpose |
|------------|---------|
| Vite 5.x | Build tool, dev server |
| React 18 | UI framework |
| TypeScript | Type safety |
| Tailwind CSS | Styling |
| shadcn/ui | Component library |
| React Query | Server state |
| React Router | Routing |
| Zustand | Client state |

## Project Structure

```
ui/agent-dashboard/
├── public/
│   ├── favicon.ico
│   └── og-image.png
├── src/
│   ├── main.tsx                    # Entry point
│   ├── App.tsx                     # Root component with router
│   ├── index.css                   # Global styles + Tailwind
│   │
│   ├── pages/
│   │   ├── Landing.tsx             # Public landing page
│   │   ├── Login.tsx               # Login page
│   │   ├── Register.tsx            # Registration page
│   │   ├── VerifyEmail.tsx         # Email verification handler
│   │   ├── ForgotPassword.tsx      # Password reset request
│   │   ├── ResetPassword.tsx       # Password reset form
│   │   ├── AuthCallback.tsx        # OAuth callback handler
│   │   ├── Dashboard.tsx           # Main dashboard
│   │   ├── Settings.tsx            # User settings
│   │   ├── Profile.tsx             # User profile
│   │   ├── Provider.tsx            # Provider profile page
│   │   ├── Leaderboards.tsx        # Leaderboards page
│   │   ├── Achievements.tsx        # Achievements page
│   │   └── Referrals.tsx           # Referral dashboard
│   │
│   ├── components/
│   │   ├── ui/                     # shadcn/ui components
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── input.tsx
│   │   │   ├── dialog.tsx
│   │   │   ├── dropdown-menu.tsx
│   │   │   ├── tabs.tsx
│   │   │   ├── toast.tsx
│   │   │   ├── tooltip.tsx
│   │   │   ├── avatar.tsx
│   │   │   ├── badge.tsx
│   │   │   ├── progress.tsx
│   │   │   ├── skeleton.tsx
│   │   │   └── ...
│   │   │
│   │   ├── Auth/
│   │   │   ├── LoginForm.tsx
│   │   │   ├── RegisterForm.tsx
│   │   │   ├── OAuthButtons.tsx
│   │   │   ├── DemoButton.tsx
│   │   │   └── ProtectedRoute.tsx
│   │   │
│   │   ├── Layout/
│   │   │   ├── AppLayout.tsx       # Authenticated layout
│   │   │   ├── Header.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   ├── MobileNav.tsx
│   │   │   └── Footer.tsx
│   │   │
│   │   ├── Landing/
│   │   │   ├── Hero.tsx
│   │   │   ├── Features.tsx
│   │   │   ├── TrustIndicators.tsx
│   │   │   ├── HowItWorks.tsx
│   │   │   ├── Comparison.tsx
│   │   │   ├── CTA.tsx
│   │   │   └── Disclaimers.tsx
│   │   │
│   │   ├── SignalStream/
│   │   │   ├── SignalStream.tsx
│   │   │   ├── SignalCard.tsx
│   │   │   ├── ScoreBreakdown.tsx
│   │   │   ├── ToolCallLog.tsx
│   │   │   ├── StrategyBreakdown.tsx
│   │   │   └── FilterBar.tsx
│   │   │
│   │   ├── Social/
│   │   │   ├── ProviderCard.tsx
│   │   │   ├── ProviderProfile.tsx
│   │   │   ├── FollowButton.tsx
│   │   │   ├── SocialFeed.tsx
│   │   │   ├── FeedSignalCard.tsx
│   │   │   ├── ReactionBar.tsx
│   │   │   ├── CommentThread.tsx
│   │   │   ├── WinCard.tsx
│   │   │   └── ShareButton.tsx
│   │   │
│   │   ├── Gamification/
│   │   │   ├── StreakBanner.tsx
│   │   │   ├── AchievementBadge.tsx
│   │   │   ├── AchievementGrid.tsx
│   │   │   ├── Leaderboard.tsx
│   │   │   └── ReferralDashboard.tsx
│   │   │
│   │   ├── Settings/
│   │   │   ├── SettingsPanel.tsx
│   │   │   ├── RiskSettings.tsx
│   │   │   ├── WatchlistManager.tsx
│   │   │   ├── NotificationSettings.tsx
│   │   │   └── ThemeToggle.tsx
│   │   │
│   │   └── Onboarding/
│   │       ├── OnboardingFlow.tsx
│   │       ├── WelcomeStep.tsx
│   │       ├── RiskToleranceStep.tsx
│   │       ├── SymbolsStep.tsx
│   │       └── NotificationsStep.tsx
│   │
│   ├── hooks/
│   │   ├── useAuth.ts              # Auth state and methods
│   │   ├── useAgentStream.ts       # SSE connection
│   │   ├── useSignals.ts           # Signal state
│   │   ├── useProviders.ts         # Provider queries
│   │   ├── useFollow.ts            # Follow actions
│   │   ├── useReaction.ts          # Reaction actions
│   │   ├── useAchievements.ts      # Achievements queries
│   │   ├── useStreaks.ts           # Streak tracking
│   │   └── useSettings.ts          # User settings
│   │
│   ├── api/
│   │   ├── client.ts               # Axios instance
│   │   ├── auth.ts                 # Auth endpoints
│   │   ├── signals.ts              # Signal endpoints
│   │   ├── providers.ts            # Provider endpoints
│   │   ├── social.ts               # Social endpoints
│   │   ├── leaderboards.ts         # Leaderboard endpoints
│   │   ├── achievements.ts         # Achievement endpoints
│   │   ├── referrals.ts            # Referral endpoints
│   │   └── user.ts                 # User settings endpoints
│   │
│   ├── stores/
│   │   ├── authStore.ts            # Auth state (Zustand)
│   │   ├── filterStore.ts          # Signal filters
│   │   └── uiStore.ts              # UI state
│   │
│   ├── lib/
│   │   ├── utils.ts                # Utility functions
│   │   └── constants.ts            # App constants
│   │
│   └── types/
│       ├── auth.ts
│       ├── signal.ts
│       ├── provider.ts
│       └── user.ts
│
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
├── postcss.config.js
├── Dockerfile
├── nginx.conf
└── README.md
```

## Page Routes

| Route | Component | Auth | Description |
|-------|-----------|------|-------------|
| `/` | Landing | No | Public landing page |
| `/login` | Login | No | Login page |
| `/register` | Register | No | Registration page |
| `/verify-email` | VerifyEmail | No | Email verification |
| `/forgot-password` | ForgotPassword | No | Password reset request |
| `/reset-password` | ResetPassword | No | Password reset form |
| `/auth/callback` | AuthCallback | No | OAuth callback |
| `/dashboard` | Dashboard | Yes/Demo | Main signal stream |
| `/dashboard/settings` | Settings | Yes | User settings |
| `/dashboard/profile` | Profile | Yes | User profile |
| `/dashboard/achievements` | Achievements | Yes | Achievement display |
| `/dashboard/referrals` | Referrals | Yes | Referral dashboard |
| `/providers` | Providers | No | Provider list |
| `/providers/:id` | Provider | No | Provider profile |
| `/leaderboards` | Leaderboards | No | Leaderboards |

## Landing Page

### Hero Section

```tsx
// src/components/Landing/Hero.tsx

import { Button } from '@/components/ui/button';
import { ArrowRight, Play } from 'lucide-react';
import { Link } from 'react-router-dom';

export function Hero() {
  return (
    <section className="relative overflow-hidden bg-gradient-to-b from-slate-900 via-slate-900 to-slate-800 py-20 lg:py-32">
      {/* Background glow */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -top-1/2 left-1/2 -translate-x-1/2 w-[800px] h-[800px] bg-blue-500/20 rounded-full blur-3xl" />
      </div>

      <div className="container relative mx-auto px-4">
        <div className="max-w-4xl mx-auto text-center">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-sm mb-8">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500" />
            </span>
            Live signals from 40M+ strategies
          </div>

          {/* Headline */}
          <h1 className="text-4xl md:text-6xl lg:text-7xl font-bold text-white mb-6 tracking-tight">
            Trading Signals Backed by{' '}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-cyan-400">
              Strategy Consensus
            </span>
          </h1>

          {/* Subheadline */}
          <p className="text-xl text-slate-400 mb-10 max-w-2xl mx-auto">
            Not just AI opinion—validated signals from millions of
            genetically-optimized strategies. Follow top providers, copy trades,
            share wins.
          </p>

          {/* CTAs */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link to="/register">
              <Button size="lg" className="w-full sm:w-auto gap-2">
                Start Free
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
            <Link to="/dashboard">
              <Button
                variant="outline"
                size="lg"
                className="w-full sm:w-auto gap-2"
              >
                <Play className="h-4 w-4" />
                Try Demo
              </Button>
            </Link>
          </div>

          {/* Social proof */}
          <div className="mt-12 flex items-center justify-center gap-8 text-sm text-slate-500">
            <div className="flex items-center gap-2">
              <span className="text-green-500 font-bold">40M+</span>
              Strategies Discovered
            </div>
            <div className="flex items-center gap-2">
              <span className="text-green-500 font-bold">70+</span>
              Strategy Types
            </div>
            <div className="flex items-center gap-2">
              <span className="text-green-500 font-bold">6mo</span>
              Forward Testing
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
```

### Trust Indicators

```tsx
// src/components/Landing/TrustIndicators.tsx

export function TrustIndicators() {
  const indicators = [
    {
      value: '40,000,000+',
      label: 'Strategies Discovered',
      description: 'Genetic algorithms finding patterns humans miss',
    },
    {
      value: '70+',
      label: 'Strategy Types',
      description: 'RSI, MACD, Bollinger, custom indicators',
    },
    {
      value: '6 months',
      label: 'Forward Testing',
      description: 'Every strategy validated in live markets',
    },
    {
      value: '5-factor',
      label: 'Opportunity Scoring',
      description: 'Confidence, return, consensus, volatility, freshness',
    },
  ];

  return (
    <section className="py-16 bg-slate-800/50">
      <div className="container mx-auto px-4">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-8">
          {indicators.map((item) => (
            <div key={item.label} className="text-center">
              <div className="text-3xl md:text-4xl font-bold text-white mb-2">
                {item.value}
              </div>
              <div className="text-sm font-medium text-slate-300 mb-1">
                {item.label}
              </div>
              <div className="text-xs text-slate-500">{item.description}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
```

### How It Works

```tsx
// src/components/Landing/HowItWorks.tsx

import { Dna, TestTube, Users, TrendingUp } from 'lucide-react';

export function HowItWorks() {
  const steps = [
    {
      icon: Dna,
      title: 'Genetic Discovery',
      description:
        'Our algorithms evolve 40M+ trading strategies using genetic optimization, finding patterns across 70+ indicator combinations.',
    },
    {
      icon: TestTube,
      title: 'Rigorous Validation',
      description:
        'Every strategy undergoes 6 months of forward testing. Walk-forward analysis ensures no overfitting to historical data.',
    },
    {
      icon: Users,
      title: 'Strategy Consensus',
      description:
        'Signals are generated when top strategies agree. Not one AI opinion—validated consensus from the best performers.',
    },
    {
      icon: TrendingUp,
      title: 'Opportunity Scoring',
      description:
        '5-factor scoring ranks opportunities by confidence, expected return, consensus strength, volatility, and freshness.',
    },
  ];

  return (
    <section className="py-20 bg-slate-900">
      <div className="container mx-auto px-4">
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
            How TradeStream Works
          </h2>
          <p className="text-slate-400 max-w-2xl mx-auto">
            Unlike traditional signal bots that rely on single algorithms,
            TradeStream leverages genetic optimization and strategy consensus.
          </p>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
          {steps.map((step, index) => (
            <div key={step.title} className="relative">
              {/* Connector line */}
              {index < steps.length - 1 && (
                <div className="hidden lg:block absolute top-12 left-1/2 w-full h-px bg-gradient-to-r from-blue-500/50 to-transparent" />
              )}

              <div className="relative bg-slate-800/50 rounded-xl p-6 border border-slate-700/50 hover:border-blue-500/50 transition-colors">
                {/* Step number */}
                <div className="absolute -top-3 -left-3 w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center text-sm font-bold">
                  {index + 1}
                </div>

                <step.icon className="h-10 w-10 text-blue-400 mb-4" />
                <h3 className="text-lg font-semibold text-white mb-2">
                  {step.title}
                </h3>
                <p className="text-sm text-slate-400">{step.description}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
```

### Disclaimers

```tsx
// src/components/Landing/Disclaimers.tsx

export function Disclaimers() {
  return (
    <section className="py-8 bg-slate-900 border-t border-slate-800">
      <div className="container mx-auto px-4">
        <div className="text-xs text-slate-500 space-y-2 max-w-4xl mx-auto">
          <p>
            <strong>Risk Disclosure:</strong> Trading involves substantial risk
            of loss and is not suitable for all investors. Past performance is
            not indicative of future results. The signals provided are for
            informational purposes only and should not be considered financial
            advice.
          </p>
          <p>
            <strong>No Guarantees:</strong> TradeStream does not guarantee
            profits or protection against losses. You should not invest money
            that you cannot afford to lose.
          </p>
          <p>
            <strong>Do Your Own Research:</strong> Always conduct your own
            research before making any investment decisions. The information
            provided should be used as a starting point for analysis, not as the
            sole basis for trading decisions.
          </p>
        </div>
      </div>
    </section>
  );
}
```

## Authentication

### useAuth Hook

```tsx
// src/hooks/useAuth.ts

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { authApi } from '@/api/auth';

interface User {
  user_id: string;
  email: string;
  display_name: string;
  avatar_url: string | null;
  is_provider: boolean;
  email_verified: boolean;
}

interface AuthState {
  user: User | null;
  accessToken: string | null;
  isDemo: boolean;
  isLoading: boolean;

  // Actions
  login: (email: string, password: string) => Promise<void>;
  loginWithOAuth: (provider: string) => void;
  loginAsDemo: () => Promise<void>;
  register: (email: string, password: string, displayName: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshToken: () => Promise<void>;
  setAccessToken: (token: string, user?: User) => void;
}

export const useAuth = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      isDemo: false,
      isLoading: false,

      login: async (email, password) => {
        set({ isLoading: true });
        try {
          const response = await authApi.login(email, password);
          set({
            user: response.user,
            accessToken: response.access_token,
            isDemo: false,
          });
        } finally {
          set({ isLoading: false });
        }
      },

      loginWithOAuth: (provider) => {
        window.location.href = `${import.meta.env.VITE_API_URL}/auth/oauth/${provider}`;
      },

      loginAsDemo: async () => {
        set({ isLoading: true });
        try {
          const response = await authApi.demo();
          set({
            user: null,
            accessToken: response.access_token,
            isDemo: true,
          });
        } finally {
          set({ isLoading: false });
        }
      },

      register: async (email, password, displayName) => {
        set({ isLoading: true });
        try {
          await authApi.register(email, password, displayName);
          // Don't auto-login, require email verification
        } finally {
          set({ isLoading: false });
        }
      },

      logout: async () => {
        try {
          await authApi.logout();
        } catch {
          // Ignore errors, clear local state anyway
        }
        set({ user: null, accessToken: null, isDemo: false });
      },

      refreshToken: async () => {
        try {
          const response = await authApi.refresh();
          set({ accessToken: response.access_token });
        } catch {
          // Refresh failed, logout
          get().logout();
        }
      },

      setAccessToken: (token, user) => {
        set({ accessToken: token, user: user ?? null, isDemo: false });
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        accessToken: state.accessToken,
        user: state.user,
        isDemo: state.isDemo,
      }),
    }
  )
);
```

### ProtectedRoute Component

```tsx
// src/components/Auth/ProtectedRoute.tsx

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
```

### OAuthButtons Component

```tsx
// src/components/Auth/OAuthButtons.tsx

import { Button } from '@/components/ui/button';
import { useAuth } from '@/hooks/useAuth';

export function OAuthButtons() {
  const { loginWithOAuth, isLoading } = useAuth();

  return (
    <div className="space-y-3">
      <Button
        variant="outline"
        className="w-full"
        onClick={() => loginWithOAuth('google')}
        disabled={isLoading}
      >
        <GoogleIcon className="mr-2 h-4 w-4" />
        Continue with Google
      </Button>

      <Button
        variant="outline"
        className="w-full"
        onClick={() => loginWithOAuth('github')}
        disabled={isLoading}
      >
        <GithubIcon className="mr-2 h-4 w-4" />
        Continue with GitHub
      </Button>
    </div>
  );
}

function GoogleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24">
      <path
        fill="currentColor"
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
      />
      <path
        fill="currentColor"
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
      />
      <path
        fill="currentColor"
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
      />
      <path
        fill="currentColor"
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
      />
    </svg>
  );
}

function GithubIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
    </svg>
  );
}
```

## Dashboard Layout

### AppLayout Component

```tsx
// src/components/Layout/AppLayout.tsx

import { Outlet } from 'react-router-dom';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { MobileNav } from './MobileNav';
import { StreakBanner } from '@/components/Gamification/StreakBanner';
import { useAuth } from '@/hooks/useAuth';

export function AppLayout() {
  const { isDemo, user } = useAuth();

  return (
    <div className="min-h-screen bg-background">
      <Header />

      <div className="flex">
        {/* Desktop sidebar */}
        <aside className="hidden lg:block w-64 border-r min-h-[calc(100vh-64px)] p-4">
          <Sidebar />
        </aside>

        {/* Main content */}
        <main className="flex-1 p-4 lg:p-6">
          {/* Demo mode banner */}
          {isDemo && (
            <div className="mb-4 p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg text-amber-500 text-sm">
              You're in demo mode.{' '}
              <a href="/register" className="underline font-medium">
                Sign up
              </a>{' '}
              to save your settings and unlock all features.
            </div>
          )}

          {/* Streak banner for logged in users */}
          {user && <StreakBanner />}

          <Outlet />
        </main>
      </div>

      {/* Mobile navigation */}
      <MobileNav />
    </div>
  );
}
```

### Header Component

```tsx
// src/components/Layout/Header.tsx

import { Link } from 'react-router-dom';
import { Bell, Settings, LogOut, User } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { useAuth } from '@/hooks/useAuth';
import { ConnectionStatus } from './ConnectionStatus';

export function Header() {
  const { user, isDemo, logout } = useAuth();

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-16 items-center justify-between px-4">
        {/* Logo */}
        <Link to="/dashboard" className="flex items-center gap-2">
          <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-cyan-500 rounded-lg" />
          <span className="font-bold text-xl">TradeStream</span>
        </Link>

        {/* Center - Connection status */}
        <ConnectionStatus />

        {/* Right - User menu */}
        <div className="flex items-center gap-4">
          {!isDemo && (
            <Button variant="ghost" size="icon">
              <Bell className="h-5 w-5" />
            </Button>
          )}

          {user ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="relative h-8 w-8 rounded-full">
                  <Avatar className="h-8 w-8">
                    <AvatarImage src={user.avatar_url || undefined} />
                    <AvatarFallback>{user.display_name[0]}</AvatarFallback>
                  </Avatar>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <div className="flex items-center gap-2 p-2">
                  <Avatar className="h-8 w-8">
                    <AvatarImage src={user.avatar_url || undefined} />
                    <AvatarFallback>{user.display_name[0]}</AvatarFallback>
                  </Avatar>
                  <div className="flex flex-col">
                    <span className="text-sm font-medium">{user.display_name}</span>
                    <span className="text-xs text-muted-foreground">{user.email}</span>
                  </div>
                </div>
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild>
                  <Link to="/dashboard/profile">
                    <User className="mr-2 h-4 w-4" />
                    Profile
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <Link to="/dashboard/settings">
                    <Settings className="mr-2 h-4 w-4" />
                    Settings
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={logout}>
                  <LogOut className="mr-2 h-4 w-4" />
                  Logout
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <Link to="/login">
              <Button>Sign In</Button>
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
```

## API Client Setup

### client.ts

```tsx
// src/api/client.ts

import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import { useAuth } from '@/hooks/useAuth';

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  withCredentials: true, // For httpOnly refresh token cookie
});

// Request interceptor - add auth token
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = useAuth.getState().accessToken;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor - handle token refresh
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && originalRequest) {
      // Try to refresh token
      try {
        await useAuth.getState().refreshToken();
        // Retry original request with new token
        return api(originalRequest);
      } catch {
        // Refresh failed, redirect to login
        useAuth.getState().logout();
        window.location.href = '/login';
      }
    }

    return Promise.reject(error);
  }
);
```

## Onboarding Flow

### OnboardingFlow Component

```tsx
// src/components/Onboarding/OnboardingFlow.tsx

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { WelcomeStep } from './WelcomeStep';
import { RiskToleranceStep } from './RiskToleranceStep';
import { SymbolsStep } from './SymbolsStep';
import { NotificationsStep } from './NotificationsStep';
import { userApi } from '@/api/user';
import { Progress } from '@/components/ui/progress';

const STEPS = ['welcome', 'risk', 'symbols', 'notifications'] as const;

export function OnboardingFlow() {
  const [step, setStep] = useState(0);
  const [data, setData] = useState({
    riskTolerance: 'moderate',
    symbols: [] as string[],
    enablePush: false,
  });
  const navigate = useNavigate();

  const handleNext = () => {
    if (step < STEPS.length - 1) {
      setStep(step + 1);
    } else {
      handleComplete();
    }
  };

  const handleBack = () => {
    if (step > 0) {
      setStep(step - 1);
    }
  };

  const handleSkip = () => {
    handleComplete();
  };

  const handleComplete = async () => {
    await userApi.updateSettings({
      risk_tolerance: data.riskTolerance,
      onboarding_completed: true,
    });

    // Add symbols to watchlist
    for (const symbol of data.symbols) {
      await userApi.addToWatchlist(symbol);
    }

    navigate('/dashboard');
  };

  const renderStep = () => {
    switch (STEPS[step]) {
      case 'welcome':
        return <WelcomeStep onNext={handleNext} onSkip={handleSkip} />;
      case 'risk':
        return (
          <RiskToleranceStep
            value={data.riskTolerance}
            onChange={(v) => setData({ ...data, riskTolerance: v })}
            onNext={handleNext}
            onBack={handleBack}
          />
        );
      case 'symbols':
        return (
          <SymbolsStep
            selected={data.symbols}
            onChange={(v) => setData({ ...data, symbols: v })}
            onNext={handleNext}
            onBack={handleBack}
          />
        );
      case 'notifications':
        return (
          <NotificationsStep
            enabled={data.enablePush}
            onChange={(v) => setData({ ...data, enablePush: v })}
            onNext={handleNext}
            onBack={handleBack}
          />
        );
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Progress */}
        <div className="mb-8">
          <Progress value={((step + 1) / STEPS.length) * 100} />
          <div className="text-sm text-slate-500 mt-2 text-center">
            Step {step + 1} of {STEPS.length}
          </div>
        </div>

        {/* Step content */}
        <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
          {renderStep()}
        </div>
      </div>
    </div>
  );
}
```

## Configuration Files

### vite.config.ts

```ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'query': ['@tanstack/react-query'],
          'ui': ['@radix-ui/react-dialog', '@radix-ui/react-dropdown-menu'],
        },
      },
    },
  },
});
```

### tailwind.config.js

```js
/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    container: {
      center: true,
      padding: '2rem',
      screens: {
        '2xl': '1400px',
      },
    },
    extend: {
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      keyframes: {
        'accordion-down': {
          from: { height: 0 },
          to: { height: 'var(--radix-accordion-content-height)' },
        },
        'accordion-up': {
          from: { height: 'var(--radix-accordion-content-height)' },
          to: { height: 0 },
        },
      },
      animation: {
        'accordion-down': 'accordion-down 0.2s ease-out',
        'accordion-up': 'accordion-up 0.2s ease-out',
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
};
```

### Dockerfile

```dockerfile
# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci

# Copy source and build
COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

### nginx.conf

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml text/javascript;

    # SPA routing - serve index.html for all routes
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API proxy
    location /api {
        proxy_pass http://gateway-api:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_cache_bypass $http_upgrade;

        # SSE-specific settings
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400s;
    }

    # Static asset caching
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
```

## Constraints

- React 18 with functional components and hooks only
- TypeScript strict mode enabled
- Bundle size < 500KB gzipped
- Initial load < 2 seconds
- Lighthouse performance score > 80
- Mobile responsive (min-width: 320px)
- Dark mode by default
- WCAG 2.1 AA accessibility

## Acceptance Criteria

- [ ] Landing page loads with hero, trust indicators, how it works
- [ ] Register form validates and submits
- [ ] Login with email/password works
- [ ] OAuth buttons redirect to providers
- [ ] OAuth callback handles token correctly
- [ ] Demo mode button works without signup
- [ ] Protected routes redirect to login
- [ ] Dashboard shows live signals via SSE
- [ ] Signal cards expand/collapse with reasoning
- [ ] Filters update signal list client-side
- [ ] Settings panel saves preferences
- [ ] Onboarding flow completes for new users
- [ ] Mobile navigation works on small screens
- [ ] Provider profiles display correctly
- [ ] Follow/unfollow updates in real-time
- [ ] Social feed shows followed providers
- [ ] Streaks display on dashboard
- [ ] Achievements page shows badges
- [ ] Referral dashboard shows stats
- [ ] Disclaimer appears on landing page
- [ ] Build produces optimized bundle
- [ ] Docker image runs correctly

## Notes

### Environment Variables

```bash
# .env.development
VITE_API_URL=http://localhost:8000

# .env.production
VITE_API_URL=https://api.tradestream.io
```

### Local Development

```bash
cd ui/agent-dashboard
npm install
npm run dev
```

### Production Build

```bash
npm run build
docker build -t tradestreamhq/agent-dashboard:v1.0.0 .
```
