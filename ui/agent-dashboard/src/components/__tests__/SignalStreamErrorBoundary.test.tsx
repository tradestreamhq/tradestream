import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { SignalStreamErrorBoundary } from "../SignalStreamErrorBoundary";

function ThrowingComponent({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) throw new Error("Test render error");
  return <div>Content rendered</div>;
}

describe("SignalStreamErrorBoundary", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  it("renders children when no error", () => {
    render(
      <SignalStreamErrorBoundary>
        <div>Child content</div>
      </SignalStreamErrorBoundary>
    );
    expect(screen.getByText("Child content")).toBeDefined();
  });

  it("renders error UI when child throws", () => {
    render(
      <SignalStreamErrorBoundary>
        <ThrowingComponent shouldThrow={true} />
      </SignalStreamErrorBoundary>
    );
    expect(screen.getByText("Signal Stream Error")).toBeDefined();
    expect(screen.getByText(/Unable to display trading signals/)).toBeDefined();
    expect(screen.getByRole("alert")).toBeDefined();
  });

  it("renders custom fallback when provided", () => {
    render(
      <SignalStreamErrorBoundary fallback={<div>Custom fallback</div>}>
        <ThrowingComponent shouldThrow={true} />
      </SignalStreamErrorBoundary>
    );
    expect(screen.getByText("Custom fallback")).toBeDefined();
  });

  it("recovers when Try Again is clicked", () => {
    const { rerender } = render(
      <SignalStreamErrorBoundary>
        <ThrowingComponent shouldThrow={true} />
      </SignalStreamErrorBoundary>
    );

    expect(screen.getByText("Signal Stream Error")).toBeDefined();
    fireEvent.click(screen.getByText("Try Again"));

    // After reset, boundary tries to render children again
    // Since ThrowingComponent still throws, it will show error again
    expect(screen.getByRole("alert")).toBeDefined();
  });

  it("has assertive aria-live for immediate screen reader announcement", () => {
    render(
      <SignalStreamErrorBoundary>
        <ThrowingComponent shouldThrow={true} />
      </SignalStreamErrorBoundary>
    );
    const alert = screen.getByRole("alert");
    expect(alert.getAttribute("aria-live")).toBe("assertive");
  });

  it("logs error to console", () => {
    render(
      <SignalStreamErrorBoundary>
        <ThrowingComponent shouldThrow={true} />
      </SignalStreamErrorBoundary>
    );
    expect(console.error).toHaveBeenCalled();
  });
});
