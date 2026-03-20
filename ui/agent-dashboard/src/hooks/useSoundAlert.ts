import { useCallback, useRef } from "react";

interface UseSoundAlertOptions {
  enabled?: boolean;
  volume?: number;
}

export function useSoundAlert({ enabled = true, volume = 0.3 }: UseSoundAlertOptions = {}) {
  const audioContextRef = useRef<AudioContext | null>(null);

  const getContext = useCallback(() => {
    if (!audioContextRef.current) {
      audioContextRef.current = new AudioContext();
    }
    return audioContextRef.current;
  }, []);

  const playTone = useCallback(
    (frequency: number, duration: number) => {
      if (!enabled) return;
      try {
        const ctx = getContext();
        const oscillator = ctx.createOscillator();
        const gainNode = ctx.createGain();

        oscillator.connect(gainNode);
        gainNode.connect(ctx.destination);

        oscillator.frequency.value = frequency;
        oscillator.type = "sine";
        gainNode.gain.setValueAtTime(volume, ctx.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);

        oscillator.start(ctx.currentTime);
        oscillator.stop(ctx.currentTime + duration);
      } catch {
        // Audio not available
      }
    },
    [enabled, volume, getContext]
  );

  const playBuyAlert = useCallback(() => playTone(880, 0.15), [playTone]);
  const playSellAlert = useCallback(() => playTone(440, 0.2), [playTone]);
  const playHotAlert = useCallback(() => {
    playTone(1046, 0.1);
    setTimeout(() => playTone(1318, 0.1), 120);
  }, [playTone]);

  return { playBuyAlert, playSellAlert, playHotAlert };
}
