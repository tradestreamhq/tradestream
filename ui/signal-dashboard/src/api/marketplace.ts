import type {
  MarketplaceListing,
  LeaderboardEntry,
  CategoryInfo,
  MarketplaceFilters,
} from "./types";

const BASE_URL = import.meta.env.VITE_MARKETPLACE_API_URL || "/api/v1/marketplace";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = localStorage.getItem("access_token");
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || `Request failed: ${res.status}`);
  }

  return res.json();
}

interface CollectionResponse<T> {
  data: Array<{ type: string; id?: string; attributes: T }>;
  meta: { total: number; limit: number; offset: number };
}

function unwrap<T>(response: CollectionResponse<T>): { items: T[]; total: number } {
  return {
    items: response.data.map((d) => d.attributes),
    total: response.meta.total,
  };
}

export async function fetchMarketplaceStrategies(
  filters?: MarketplaceFilters,
  limit = 50,
  offset = 0
): Promise<{ items: MarketplaceListing[]; total: number }> {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  if (filters?.category) params.set("category", filters.category);
  if (filters?.search) params.set("search", filters.search);
  if (filters?.order_by) params.set("order_by", filters.order_by);
  const qs = params.toString();
  const resp = await request<CollectionResponse<MarketplaceListing>>(
    `/strategies?${qs}`
  );
  return unwrap(resp);
}

export async function fetchLeaderboard(
  period = "monthly",
  sortBy = "total_return_pct",
  category?: string,
  limit = 50,
  offset = 0
): Promise<{ items: LeaderboardEntry[]; total: number }> {
  const params = new URLSearchParams();
  params.set("period", period);
  params.set("sort_by", sortBy);
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  if (category) params.set("category", category);
  const qs = params.toString();
  const resp = await request<CollectionResponse<LeaderboardEntry>>(
    `/leaderboard?${qs}`
  );
  return unwrap(resp);
}

export async function fetchCategories(): Promise<CategoryInfo[]> {
  const resp = await request<CollectionResponse<CategoryInfo>>(
    "/strategies/categories"
  );
  return unwrap(resp).items;
}

export async function subscribeToStrategy(
  listingId: string,
  userId: string
): Promise<void> {
  await request(`/strategies/${listingId}/subscribe`, {
    method: "POST",
    body: JSON.stringify({ user_id: userId }),
  });
}

export async function unsubscribeFromStrategy(
  listingId: string,
  userId: string
): Promise<void> {
  await request(`/strategies/${listingId}/subscribe?user_id=${userId}`, {
    method: "DELETE",
  });
}

export async function compareStrategies(
  ids: string[],
  period = "all_time"
): Promise<MarketplaceListing[]> {
  const resp = await request<CollectionResponse<MarketplaceListing>>(
    `/compare?ids=${ids.join(",")}&period=${period}`
  );
  return unwrap(resp).items;
}
