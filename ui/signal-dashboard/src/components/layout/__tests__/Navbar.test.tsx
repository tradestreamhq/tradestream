import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { Navbar } from "../Navbar";
import * as AuthContext from "@/context/AuthContext";

vi.mock("@/context/AuthContext", () => ({
  useAuth: vi.fn(),
}));

function renderNavbar(authOverrides = {}) {
  const defaultAuth = {
    user: null,
    isLoading: false,
    isAuthenticated: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn(),
  };

  vi.mocked(AuthContext.useAuth).mockReturnValue({
    ...defaultAuth,
    ...authOverrides,
  });

  return render(
    <MemoryRouter>
      <Navbar />
    </MemoryRouter>
  );
}

describe("Navbar", () => {
  it("shows sign in and get started when not authenticated", () => {
    renderNavbar();
    expect(screen.getByText("Sign In")).toBeInTheDocument();
    expect(screen.getByText("Get Started")).toBeInTheDocument();
  });

  it("shows nav links when authenticated", () => {
    renderNavbar({
      isAuthenticated: true,
      user: { name: "Alice", email: "alice@test.com" },
    });
    expect(screen.getByText("Signals")).toBeInTheDocument();
    expect(screen.getByText("Strategies")).toBeInTheDocument();
    expect(screen.getByText("History")).toBeInTheDocument();
    expect(screen.getByText("Alice")).toBeInTheDocument();
  });

  it("shows sign out when authenticated", () => {
    const logout = vi.fn();
    renderNavbar({
      isAuthenticated: true,
      user: { name: "Alice" },
      logout,
    });
    expect(screen.getByText("Sign Out")).toBeInTheDocument();
  });

  it("toggles mobile menu", () => {
    renderNavbar();
    const toggle = screen.getByLabelText("Toggle navigation menu");
    fireEvent.click(toggle);
    // Mobile menu should be visible - check for mobile sign in link
    const signInLinks = screen.getAllByText("Sign In");
    expect(signInLinks.length).toBeGreaterThanOrEqual(2);
  });

  it("renders TradeStream brand link", () => {
    renderNavbar();
    expect(screen.getByText("TradeStream")).toBeInTheDocument();
  });
});
