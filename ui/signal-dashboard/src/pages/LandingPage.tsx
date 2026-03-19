import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import type { PerformanceStats, PricingPlan } from "@/api/types";
import { fetchPerformanceStats } from "@/api/client";
import { formatPercent } from "@/lib/utils";

const PRICING_PLANS: PricingPlan[] = [
  {
    id: "free",
    name: "Free",
    price: 0,
    interval: "month",
    signals_limit: 10,
    features: [
      "10 signals per month",
      "Basic strategy insights",
      "Email alerts",
      "Community access",
    ],
  },
  {
    id: "starter",
    name: "Starter",
    price: 29,
    interval: "month",
    signals_limit: 100,
    features: [
      "100 signals per month",
      "Real-time signal feed",
      "Strategy leaderboard",
      "Signal history & analytics",
      "Telegram alerts",
    ],
  },
  {
    id: "pro",
    name: "Pro",
    price: 79,
    interval: "month",
    signals_limit: -1,
    highlighted: true,
    features: [
      "Unlimited signals",
      "Real-time signal feed",
      "Full strategy analytics",
      "Priority Telegram alerts",
      "API access",
      "Advanced filters",
    ],
  },
  {
    id: "enterprise",
    name: "Enterprise",
    price: 199,
    interval: "month",
    signals_limit: -1,
    features: [
      "Everything in Pro",
      "Custom strategies",
      "Dedicated support",
      "SLA guarantees",
      "Webhook integrations",
      "White-label options",
    ],
  },
];

const FEATURES = [
  {
    title: "AI-Powered Signals",
    description:
      "Multi-strategy analysis combining technical indicators, market sentiment, and volatility scoring.",
    icon: (
      <svg className="h-8 w-8 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" />
      </svg>
    ),
  },
  {
    title: "Real-Time Delivery",
    description:
      "Signals delivered instantly via dashboard, Telegram, and API with sub-second latency.",
    icon: (
      <svg className="h-8 w-8 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
      </svg>
    ),
  },
  {
    title: "Strategy Rankings",
    description:
      "Transparent leaderboard ranking strategies by win rate, Sharpe ratio, and total return.",
    icon: (
      <svg className="h-8 w-8 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
      </svg>
    ),
  },
  {
    title: "Full Signal History",
    description:
      "Browse and filter all past signals with outcomes, P&L tracking, and performance analytics.",
    icon: (
      <svg className="h-8 w-8 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
];

export function LandingPage() {
  const [stats, setStats] = useState<PerformanceStats | null>(null);

  useEffect(() => {
    fetchPerformanceStats().then(setStats).catch(() => {});
  }, []);

  return (
    <div>
      {/* Hero */}
      <section className="relative overflow-hidden px-4 py-20 text-center sm:px-6 sm:py-32">
        <div className="absolute inset-0 -z-10 bg-gradient-to-b from-brand-900/20 to-transparent" />
        <h1 className="mx-auto max-w-4xl text-4xl font-extrabold tracking-tight sm:text-6xl">
          <span className="bg-gradient-to-r from-cyan-400 to-brand-400 bg-clip-text text-transparent">
            AI-Powered Trading Signals
          </span>
          <br />
          <span className="text-white">Delivered in Real Time</span>
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-slate-400">
          Multi-strategy analysis across crypto markets. Get actionable BUY/SELL
          signals with confidence scores, entry/exit levels, and transparent
          reasoning.
        </p>
        <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
          <Link to="/register" className="btn-primary px-8 py-3.5 text-base">
            Start Free Trial
          </Link>
          <Link to="/signals" className="btn-secondary px-8 py-3.5 text-base">
            View Live Signals
          </Link>
        </div>
      </section>

      {/* Stats bar */}
      {stats && (
        <section className="border-y border-slate-700/50 bg-surface-card/50 py-8">
          <div className="mx-auto grid max-w-5xl grid-cols-2 gap-6 px-4 sm:grid-cols-4 sm:px-6">
            <StatItem
              label="Signals Generated"
              value={stats.total_signals.toLocaleString()}
            />
            <StatItem label="Win Rate" value={formatPercent(stats.win_rate)} />
            <StatItem
              label="Avg Return"
              value={`${(stats.avg_return * 100).toFixed(1)}%`}
            />
            <StatItem
              label="Active Strategies"
              value={String(stats.active_strategies)}
            />
          </div>
        </section>
      )}

      {/* Features */}
      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6">
        <h2 className="text-center text-3xl font-bold text-white">
          How It Works
        </h2>
        <p className="mx-auto mt-4 max-w-2xl text-center text-slate-400">
          Our AI agents analyze multiple trading strategies simultaneously,
          scoring and ranking signals to surface the best opportunities.
        </p>
        <div className="mt-16 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map((f) => (
            <div key={f.title} className="card">
              <div className="mb-4">{f.icon}</div>
              <h3 className="text-lg font-semibold text-white">{f.title}</h3>
              <p className="mt-2 text-sm text-slate-400">{f.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Pricing */}
      <section
        id="pricing"
        className="border-t border-slate-700/50 bg-surface-card/30 px-4 py-20 sm:px-6"
      >
        <h2 className="text-center text-3xl font-bold text-white">
          Simple Pricing
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-center text-slate-400">
          Start free, upgrade when you need more signals.
        </p>
        <div className="mx-auto mt-12 grid max-w-6xl gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {PRICING_PLANS.map((plan) => (
            <div
              key={plan.id}
              className={`card flex flex-col ${
                plan.highlighted
                  ? "ring-2 ring-brand-500"
                  : ""
              }`}
            >
              {plan.highlighted && (
                <span className="badge mb-4 self-start bg-brand-500/20 text-brand-400">
                  Most Popular
                </span>
              )}
              <h3 className="text-lg font-semibold text-white">{plan.name}</h3>
              <div className="mt-2">
                <span className="text-3xl font-bold text-white">
                  ${plan.price}
                </span>
                <span className="text-sm text-slate-400">
                  /{plan.interval}
                </span>
              </div>
              <p className="mt-2 text-sm text-slate-500">
                {plan.signals_limit === -1
                  ? "Unlimited signals"
                  : `${plan.signals_limit} signals/mo`}
              </p>
              <ul className="mt-6 flex-1 space-y-3">
                {plan.features.map((feat) => (
                  <li
                    key={feat}
                    className="flex items-start gap-2 text-sm text-slate-300"
                  >
                    <svg
                      className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M5 13l4 4L19 7"
                      />
                    </svg>
                    {feat}
                  </li>
                ))}
              </ul>
              <Link
                to="/register"
                className={`mt-6 text-center ${
                  plan.highlighted ? "btn-primary" : "btn-secondary"
                }`}
              >
                {plan.price === 0 ? "Get Started" : "Subscribe"}
              </Link>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="px-4 py-20 text-center sm:px-6">
        <h2 className="text-3xl font-bold text-white">
          Ready to Trade Smarter?
        </h2>
        <p className="mx-auto mt-4 max-w-lg text-slate-400">
          Join thousands of traders using AI-powered signals to make better
          decisions.
        </p>
        <Link
          to="/register"
          className="btn-primary mt-8 inline-block px-10 py-4 text-base"
        >
          Create Free Account
        </Link>
      </section>
    </div>
  );
}

function StatItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="text-center">
      <div className="text-2xl font-bold text-white">{value}</div>
      <div className="mt-1 text-sm text-slate-400">{label}</div>
    </div>
  );
}
