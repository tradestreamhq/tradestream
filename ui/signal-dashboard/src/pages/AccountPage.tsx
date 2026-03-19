import { useAuth } from "@/context/AuthContext";
import { cn, formatPercent } from "@/lib/utils";

const PLAN_LABELS: Record<string, string> = {
  free: "Free",
  starter: "Starter",
  pro: "Pro",
  enterprise: "Enterprise",
};

export function AccountPage() {
  const { user } = useAuth();

  if (!user) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-8 sm:px-6">
        <div className="card text-center text-slate-400">
          Loading account details...
        </div>
      </div>
    );
  }

  const usagePercent =
    user.signals_limit > 0 ? user.signals_used / user.signals_limit : 0;
  const isUnlimited = user.signals_limit === -1;

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
      <h1 className="mb-6 text-2xl font-bold text-white">Account</h1>

      {/* Profile */}
      <section className="card mb-6">
        <h2 className="mb-4 text-lg font-semibold text-white">Profile</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <div className="text-xs text-slate-500">Name</div>
            <div className="text-sm text-white">{user.name}</div>
          </div>
          <div>
            <div className="text-xs text-slate-500">Email</div>
            <div className="text-sm text-white">{user.email}</div>
          </div>
        </div>
      </section>

      {/* Subscription */}
      <section className="card mb-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white">Subscription</h2>
          <span
            className={cn(
              "badge",
              user.subscription_status === "active" &&
                "bg-emerald-500/20 text-emerald-400",
              user.subscription_status === "cancelled" &&
                "bg-red-500/20 text-red-400",
              user.subscription_status === "past_due" &&
                "bg-amber-500/20 text-amber-400"
            )}
          >
            {user.subscription_status}
          </span>
        </div>

        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <div>
            <div className="text-xs text-slate-500">Current Plan</div>
            <div className="text-lg font-semibold text-brand-400">
              {PLAN_LABELS[user.plan] || user.plan}
            </div>
          </div>
          <div>
            <div className="text-xs text-slate-500">Period Ends</div>
            <div className="text-sm text-white">
              {new Date(user.current_period_end).toLocaleDateString()}
            </div>
          </div>
        </div>

        <div className="mt-6">
          <div className="flex items-center justify-between text-sm">
            <span className="text-slate-400">Signal Usage</span>
            <span className="text-white">
              {user.signals_used}
              {isUnlimited ? " / Unlimited" : ` / ${user.signals_limit}`}
            </span>
          </div>
          {!isUnlimited && (
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-700">
              <div
                className={cn(
                  "h-full rounded-full transition-all",
                  usagePercent > 0.9
                    ? "bg-red-500"
                    : usagePercent > 0.7
                      ? "bg-amber-500"
                      : "bg-brand-500"
                )}
                style={{ width: `${Math.min(usagePercent * 100, 100)}%` }}
              />
            </div>
          )}
        </div>

        <div className="mt-6 flex flex-wrap gap-3">
          {user.plan !== "pro" && (
            <a href="#pricing" className="btn-primary text-sm">
              Upgrade Plan
            </a>
          )}
          <button className="btn-secondary text-sm">
            Manage Billing
          </button>
        </div>
      </section>

      {/* Quick stats */}
      <section className="card">
        <h2 className="mb-4 text-lg font-semibold text-white">
          Usage Summary
        </h2>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          <div>
            <div className="text-2xl font-bold text-white">
              {user.signals_used}
            </div>
            <div className="text-xs text-slate-400">Signals Used</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-white">
              {isUnlimited
                ? "\u221E"
                : String(user.signals_limit - user.signals_used)}
            </div>
            <div className="text-xs text-slate-400">Remaining</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-white">
              {isUnlimited ? "100%" : formatPercent(usagePercent)}
            </div>
            <div className="text-xs text-slate-400">Utilization</div>
          </div>
        </div>
      </section>
    </div>
  );
}
