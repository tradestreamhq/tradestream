import { describe, it, expect } from "vitest";
import { cn, formatPercent, formatPrice, timeAgo } from "../utils";

describe("cn", () => {
  it("joins truthy class names", () => {
    expect(cn("a", "b", "c")).toBe("a b c");
  });

  it("filters falsy values", () => {
    expect(cn("a", false, null, undefined, "b")).toBe("a b");
  });

  it("returns empty string for no args", () => {
    expect(cn()).toBe("");
  });
});

describe("formatPercent", () => {
  it("formats decimal as percentage", () => {
    expect(formatPercent(0.856)).toBe("85.6%");
  });

  it("handles zero", () => {
    expect(formatPercent(0)).toBe("0.0%");
  });

  it("handles 1.0", () => {
    expect(formatPercent(1)).toBe("100.0%");
  });
});

describe("formatPrice", () => {
  it("formats with two decimal places", () => {
    expect(formatPrice(42000)).toBe("42,000.00");
  });

  it("formats small values", () => {
    expect(formatPrice(0.5)).toBe("0.50");
  });
});

describe("timeAgo", () => {
  it("shows seconds ago", () => {
    const now = new Date(Date.now() - 30000).toISOString();
    expect(timeAgo(now)).toBe("30s ago");
  });

  it("shows minutes ago", () => {
    const now = new Date(Date.now() - 300000).toISOString();
    expect(timeAgo(now)).toBe("5m ago");
  });

  it("shows hours ago", () => {
    const now = new Date(Date.now() - 7200000).toISOString();
    expect(timeAgo(now)).toBe("2h ago");
  });
});
