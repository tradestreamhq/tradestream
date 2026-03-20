import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { useDebounce } from "../useDebounce";

describe("useDebounce", () => {
  it("returns initial value immediately", () => {
    const { result } = renderHook(() => useDebounce(42, 150));
    expect(result.current).toBe(42);
  });

  it("debounces value changes", () => {
    vi.useFakeTimers();

    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 150),
      { initialProps: { value: 0 } }
    );

    // Change value
    rerender({ value: 50 });
    expect(result.current).toBe(0); // Not yet updated

    // Advance time partially
    act(() => {
      vi.advanceTimersByTime(100);
    });
    expect(result.current).toBe(0); // Still not updated

    // Advance past delay
    act(() => {
      vi.advanceTimersByTime(60);
    });
    expect(result.current).toBe(50); // Now updated

    vi.useRealTimers();
  });

  it("resets timer on rapid changes", () => {
    vi.useFakeTimers();

    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 150),
      { initialProps: { value: 0 } }
    );

    rerender({ value: 25 });
    act(() => {
      vi.advanceTimersByTime(100);
    });

    rerender({ value: 75 });
    act(() => {
      vi.advanceTimersByTime(100);
    });
    expect(result.current).toBe(0); // Neither update applied yet

    act(() => {
      vi.advanceTimersByTime(60);
    });
    expect(result.current).toBe(75); // Only final value applied

    vi.useRealTimers();
  });
});
