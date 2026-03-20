import { useCallback, useRef, useEffect } from "react";

interface UseSoundAlertOptions {
  enabled?: boolean;
  volume?: number;
}

/**
 * Plays a short synthesized beep when triggerAlert() is called.
 * Uses the Web Audio API — no external sound files needed.
 */
export function useSoundAlert({
  enabled = true,
  volume = 0.3,
}: UseSoundAlertOptions = {}) {
  const ctxRef = useRef<AudioContext | null>(null);
  const enabledRef = useRef(enabled);

  useEffect(() => {
    enabledRef.current = enabled;
  }, [enabled]);

  const triggerAlert = useCallback(
    (type: "buy" | "sell" | "default" = "default") => {
      if (!enabledRef.current) return;

      try {
        if (!ctxRef.current) {
          ctxRef.current = new AudioContext();
        }

        const ctx = ctxRef.current;
        const oscillator = ctx.createOscillator();
        const gain = ctx.createGain();

        oscillator.connect(gain);
        gain.connect(ctx.destination);

        // Different tones for different signal types
        const freq = type === "buy" ? 880 : type === "sell" ? 440 : 660;
        oscillator.frequency.setValueAtTime(freq, ctx.currentTime);
        oscillator.type = "sine";

        gain.gain.setValueAtTime(volume, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.15);

        oscillator.start(ctx.currentTime);
        oscillator.stop(ctx.currentTime + 0.15);
      } catch {
        // Audio not available — silently ignore
      }
    },
    [volume]
  );

  return { triggerAlert };
}
