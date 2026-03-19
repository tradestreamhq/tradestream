import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { AccountPage } from "../AccountPage";
import * as AuthContext from "@/context/AuthContext";
import type { User } from "@/api/types";

vi.mock("@/context/AuthContext", () => ({
  useAuth: vi.fn(),
}));

const mockUser: User = {
  user_id: "u1",
  email: "trader@example.com",
  name: "Jane Trader",
  plan: "starter",
  signals_used: 42,
  signals_limit: 100,
  subscription_status: "active",
  current_period_end: "2026-04-19T00:00:00Z",
};

function renderAccount(user: User | null = mockUser) {
  vi.mocked(AuthContext.useAuth).mockReturnValue({
    user,
    isLoading: false,
    isAuthenticated: !!user,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn(),
  });
  return render(<AccountPage />);
}

describe("AccountPage", () => {
  it("shows loading when user is null", () => {
    renderAccount(null);
    expect(screen.getByText("Loading account details...")).toBeInTheDocument();
  });

  it("displays user profile info", () => {
    renderAccount();
    expect(screen.getByText("Jane Trader")).toBeInTheDocument();
    expect(screen.getByText("trader@example.com")).toBeInTheDocument();
  });

  it("shows subscription status", () => {
    renderAccount();
    expect(screen.getByText("active")).toBeInTheDocument();
    expect(screen.getByText("Starter")).toBeInTheDocument();
  });

  it("shows signal usage stats", () => {
    renderAccount();
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("42 / 100")).toBeInTheDocument();
  });

  it("shows upgrade plan link for non-pro users", () => {
    renderAccount();
    expect(screen.getByText("Upgrade Plan")).toBeInTheDocument();
  });

  it("hides upgrade plan link for pro users", () => {
    renderAccount({ ...mockUser, plan: "pro" });
    expect(screen.queryByText("Upgrade Plan")).not.toBeInTheDocument();
  });

  it("shows unlimited for unlimited plans", () => {
    renderAccount({ ...mockUser, signals_limit: -1 });
    expect(screen.getByText("42 / Unlimited")).toBeInTheDocument();
  });
});
