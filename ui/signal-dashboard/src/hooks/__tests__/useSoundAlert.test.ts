import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useSoundAlert } from "../useSoundAlert";

const mockStop = vi.fn();
const mockStart = vi.fn();
const mockConnect = vi.fn();
const mockSetValueAtTime = vi.fn();
const mockExponentialRampToValueAtTime = vi.fn();

const mockOscillator = {
  connect: mockConnect,
  frequency: { setValueAtTime: mockSetValueAtTime },
  type: "sine",
  start: mockStart,
  stop: mockStop,
};

const mockGainNode = {
  connect: mockConnect,
  gain: {
    setValueAtTime: mockSetValueAtTime,
    exponentialRampToValueAtTime: mockExponentialRampToValueAtTime,
  },
};

const mockAudioContext = {
  createOscillator: vi.fn(() => mockOscillator),
  createGain: vi.fn(() => mockGainNode),
  destination: {},
  currentTime: 0,
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal(
    "AudioContext",
    vi.fn(() => mockAudioContext)
  );
});

describe("useSoundAlert", () => {
  it("creates AudioContext and plays tone on triggerAlert", () => {
    const { result } = renderHook(() => useSoundAlert({ enabled: true }));

    act(() => {
      result.current.triggerAlert("buy");
    });

    expect(mockAudioContext.createOscillator).toHaveBeenCalled();
    expect(mockAudioContext.createGain).toHaveBeenCalled();
    expect(mockStart).toHaveBeenCalled();
    expect(mockStop).toHaveBeenCalled();
  });

  it("does not play when disabled", () => {
    const { result } = renderHook(() => useSoundAlert({ enabled: false }));

    act(() => {
      result.current.triggerAlert("buy");
    });

    expect(mockAudioContext.createOscillator).not.toHaveBeenCalled();
  });

  it("sets different frequencies for buy, sell, and default", () => {
    const { result } = renderHook(() => useSoundAlert({ enabled: true }));

    act(() => {
      result.current.triggerAlert("buy");
    });
    expect(mockSetValueAtTime).toHaveBeenCalledWith(880, 0);

    vi.clearAllMocks();
    act(() => {
      result.current.triggerAlert("sell");
    });
    expect(mockSetValueAtTime).toHaveBeenCalledWith(440, 0);

    vi.clearAllMocks();
    act(() => {
      result.current.triggerAlert("default");
    });
    expect(mockSetValueAtTime).toHaveBeenCalledWith(660, 0);
  });

  it("silently handles AudioContext errors", () => {
    vi.stubGlobal(
      "AudioContext",
      vi.fn(() => {
        throw new Error("Not supported");
      })
    );

    const { result } = renderHook(() => useSoundAlert({ enabled: true }));

    expect(() => {
      act(() => {
        result.current.triggerAlert("buy");
      });
    }).not.toThrow();
  });
});
