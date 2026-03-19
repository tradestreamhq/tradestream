import type {
  Signal,
  Strategy,
  User,
  SignalFilters,
  PerformanceStats,
  AuthTokens,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_URL || "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = localStorage.getItem("access_token");
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  if (res.status === 401) {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || `Request failed: ${res.status}`);
  }

  return res.json();
}

export async function fetchSignals(
  filters?: SignalFilters
): Promise<Signal[]> {
  const params = new URLSearchParams();
  if (filters?.symbols?.length)
    params.set("symbols", filters.symbols.join(","));
  if (filters?.actions?.length)
    params.set("actions", filters.actions.join(","));
  if (filters?.outcomes?.length)
    params.set("outcomes", filters.outcomes.join(","));
  if (filters?.minConfidence)
    params.set("min_confidence", String(filters.minConfidence));
  if (filters?.dateFrom) params.set("date_from", filters.dateFrom);
  if (filters?.dateTo) params.set("date_to", filters.dateTo);
  const qs = params.toString();
  return request<Signal[]>(`/signals${qs ? `?${qs}` : ""}`);
}

export async function fetchLiveSignals(): Promise<Signal[]> {
  return request<Signal[]>("/signals/live");
}

export async function fetchStrategies(): Promise<Strategy[]> {
  return request<Strategy[]>("/strategies");
}

export async function fetchPerformanceStats(): Promise<PerformanceStats> {
  return request<PerformanceStats>("/stats/performance");
}

export async function fetchUser(): Promise<User> {
  return request<User>("/user/me");
}

export async function updateSubscription(planId: string): Promise<void> {
  await request("/user/subscription", {
    method: "POST",
    body: JSON.stringify({ plan_id: planId }),
  });
}

export async function login(
  email: string,
  password: string
): Promise<AuthTokens> {
  return request<AuthTokens>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function register(
  email: string,
  password: string,
  name: string
): Promise<AuthTokens> {
  return request<AuthTokens>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, name }),
  });
}

export async function requestPasswordReset(email: string): Promise<void> {
  await request("/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export function createSignalStream(
  onSignal: (signal: Signal) => void,
  onError?: (error: Event) => void
): EventSource {
  const token = localStorage.getItem("access_token");
  const url = `${BASE_URL}/signals/stream${token ? `?token=${token}` : ""}`;
  const source = new EventSource(url);

  source.addEventListener("signal", (e) => {
    const signal = JSON.parse((e as MessageEvent).data) as Signal;
    onSignal(signal);
  });

  source.onerror = (e) => {
    onError?.(e);
  };

  return source;
}
