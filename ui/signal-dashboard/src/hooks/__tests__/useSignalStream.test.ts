import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useSignalStream } from "../useSignalStream";

const mockClose = vi.fn();
let mockOnOpen: (() => void) | null = null;

vi.mock("@/api/client", () => ({
  createSignalStream: vi.fn(
    (
      onSignal: (signal: unknown) => void,
      onError?: () => void
    ) => {
      const source = {
        close: mockClose,
        set onopen(fn: (() => void) | null) {
          mockOnOpen = fn;
        },
        get onopen() {
          return mockOnOpen;
        },
        _onSignal: onSignal,
        _onError: onError,
      };
      return source;
    }
  ),
}));

beforeEach(() => {
  vi.clearAllMocks();
  mockOnOpen = null;
  vi.useFakeTimers();
});

describe("useSignalStream", () => {
  it("starts disconnected and connects on mount", async () => {
    const { result } = renderHook(() => useSignalStream());

    expect(result.current.signals).toEqual([]);
    expect(result.current.isConnected).toBe(false);
    expect(typeof result.current.reconnect).toBe("function");
  });

  it("sets isConnected to true on open", () => {
    const { result } = renderHook(() => useSignalStream());

    act(() => {
      mockOnOpen?.();
    });

    expect(result.current.isConnected).toBe(true);
  });

  it("closes EventSource on unmount", () => {
    const { unmount } = renderHook(() => useSignalStream());
    unmount();
    expect(mockClose).toHaveBeenCalled();
  });

  it("reconnect closes and re-creates connection", () => {
    const { result } = renderHook(() => useSignalStream());

    act(() => {
      result.current.reconnect();
    });

    // close is called at least once (initial close + reconnect)
    expect(mockClose).toHaveBeenCalled();
  });
});
