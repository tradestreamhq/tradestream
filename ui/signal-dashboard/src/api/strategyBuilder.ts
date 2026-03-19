/**
 * API client for the User Strategy Builder service.
 */

const BASE_URL = import.meta.env.VITE_API_URL || "/api";
const BUILDER_URL = `${BASE_URL}/v1/strategy-builder`;

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = localStorage.getItem("access_token");
  const userId = localStorage.getItem("user_id") || "anonymous";
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-User-Id": userId,
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };

  const res = await fetch(`${BUILDER_URL}${path}`, { ...options, headers });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: { message: `Request failed: ${res.status}` } }));
    throw { status: res.status, ...body };
  }

  if (res.status === 204) return null as T;
  return res.json();
}

// --- Types ---

export interface IndicatorParam {
  name: string;
  type: "integer" | "double";
  default: number;
  min: number;
  max: number;
  description: string;
}

export interface IndicatorSpec {
  type: string;
  name: string;
  category: string;
  description: string;
  inputs: string[];
  params: IndicatorParam[];
  outputs: string[];
}

export interface ConditionSpec {
  type: string;
  description: string;
  requires: string[];
  category: string;
}

export interface IndicatorConfig {
  id: string;
  type: string;
  input: string;
  params: Record<string, number>;
}

export interface ConditionConfig {
  type: string;
  indicator: string | null;
  params: Record<string, unknown>;
}

export interface UserStrategy {
  id: string;
  user_id: string;
  name: string;
  description: string;
  category: string;
  indicators: IndicatorConfig[];
  entry_conditions: ConditionConfig[];
  exit_conditions: ConditionConfig[];
  tags: string[];
  version: number;
  is_published: boolean;
  backtest_results: BacktestResult | null;
  created_at: string;
  updated_at: string;
}

export interface BacktestResult {
  total_return_pct: number;
  sharpe_ratio: number;
  win_rate: number;
  max_drawdown_pct: number;
  total_trades: number;
  trades?: Array<{ entry_price: number; exit_price: number; pnl_pct: number }>;
  candles_analyzed: number;
}

export interface ValidationResult {
  valid: boolean;
  errors: Array<{ field: string; message: string }>;
  indicator_count: number;
  entry_condition_count: number;
  exit_condition_count: number;
}

export interface ApiResponse<T> {
  data: {
    type: string;
    id?: string;
    attributes: T;
  };
}

export interface CollectionResponse<T> {
  data: Array<{
    type: string;
    id?: string;
    attributes: T;
  }>;
  meta: { total: number; limit: number; offset: number };
}

// --- Palette ---

export async function fetchIndicators(
  category?: string
): Promise<CollectionResponse<IndicatorSpec>> {
  const params = category ? `?category=${category}` : "";
  return request(`/palette/indicators${params}`);
}

export async function fetchIndicator(
  type: string
): Promise<ApiResponse<IndicatorSpec>> {
  return request(`/palette/indicators/${type}`);
}

export async function fetchConditions(): Promise<
  CollectionResponse<ConditionSpec>
> {
  return request("/palette/conditions");
}

export async function fetchIndicatorCategories(): Promise<
  CollectionResponse<{ name: string; count: number }>
> {
  return request("/palette/categories");
}

// --- Strategy CRUD ---

export async function createStrategy(config: {
  name: string;
  description?: string;
  category?: string;
  indicators: IndicatorConfig[];
  entry_conditions: ConditionConfig[];
  exit_conditions: ConditionConfig[];
  tags?: string[];
}): Promise<ApiResponse<UserStrategy>> {
  return request("/strategies", {
    method: "POST",
    body: JSON.stringify(config),
  });
}

export async function listStrategies(params?: {
  category?: string;
  search?: string;
  limit?: number;
  offset?: number;
}): Promise<CollectionResponse<UserStrategy>> {
  const qs = new URLSearchParams();
  if (params?.category) qs.set("category", params.category);
  if (params?.search) qs.set("search", params.search);
  if (params?.limit) qs.set("limit", String(params.limit));
  if (params?.offset) qs.set("offset", String(params.offset));
  const query = qs.toString();
  return request(`/strategies${query ? `?${query}` : ""}`);
}

export async function getStrategy(
  id: string
): Promise<ApiResponse<UserStrategy>> {
  return request(`/strategies/${id}`);
}

export async function updateStrategy(
  id: string,
  update: Record<string, unknown>
): Promise<ApiResponse<UserStrategy>> {
  return request(`/strategies/${id}`, {
    method: "PUT",
    body: JSON.stringify(update),
  });
}

export async function deleteStrategy(id: string): Promise<void> {
  return request(`/strategies/${id}`, { method: "DELETE" });
}

// --- Validation ---

export async function validateStrategy(config: {
  name: string;
  indicators: IndicatorConfig[];
  entry_conditions: ConditionConfig[];
  exit_conditions: ConditionConfig[];
}): Promise<ApiResponse<ValidationResult>> {
  return request("/strategies/validate", {
    method: "POST",
    body: JSON.stringify(config),
  });
}

// --- Backtest ---

export async function backtestStrategy(
  id: string,
  params: {
    symbol: string;
    timeframe?: string;
    start_date?: string;
    end_date?: string;
  }
): Promise<ApiResponse<BacktestResult>> {
  return request(`/strategies/${id}/backtest`, {
    method: "POST",
    body: JSON.stringify(params),
  });
}

// --- Publish ---

export async function publishStrategy(
  id: string,
  params: { price?: number; author?: string }
): Promise<ApiResponse<unknown>> {
  return request(`/strategies/${id}/publish`, {
    method: "POST",
    body: JSON.stringify(params),
  });
}
