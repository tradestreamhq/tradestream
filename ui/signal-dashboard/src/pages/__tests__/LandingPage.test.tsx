import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { LandingPage } from "../LandingPage";

vi.mock("@/api/client", () => ({
  fetchPerformanceStats: vi.fn().mockResolvedValue({
    total_signals: 12500,
    win_rate: 0.72,
    avg_return: 0.028,
    total_return: 1.45,
    active_strategies: 15,
    subscribers: 3200,
  }),
}));

describe("LandingPage", () => {
  it("renders hero section", () => {
    render(
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>
    );

    expect(screen.getByText("AI-Powered Trading Signals")).toBeInTheDocument();
    expect(screen.getByText("Delivered in Real Time")).toBeInTheDocument();
  });

  it("renders feature cards", () => {
    render(
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>
    );

    expect(screen.getByText("AI-Powered Signals")).toBeInTheDocument();
    expect(screen.getByText("Real-Time Delivery")).toBeInTheDocument();
    expect(screen.getByText("Strategy Rankings")).toBeInTheDocument();
    expect(screen.getByText("Full Signal History")).toBeInTheDocument();
  });

  it("renders pricing plans", () => {
    render(
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>
    );

    expect(screen.getByText("Free")).toBeInTheDocument();
    expect(screen.getByText("Starter")).toBeInTheDocument();
    expect(screen.getByText("Pro")).toBeInTheDocument();
    expect(screen.getByText("Enterprise")).toBeInTheDocument();
    expect(screen.getByText("Most Popular")).toBeInTheDocument();
  });

  it("renders CTA section", () => {
    render(
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>
    );

    expect(
      screen.getByText("Ready to Trade Smarter?")
    ).toBeInTheDocument();
    expect(screen.getByText("Create Free Account")).toBeInTheDocument();
  });

  it("renders signup links", () => {
    render(
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>
    );

    expect(screen.getByText("Start Free Trial")).toBeInTheDocument();
    expect(screen.getByText("View Live Signals")).toBeInTheDocument();
  });
});
