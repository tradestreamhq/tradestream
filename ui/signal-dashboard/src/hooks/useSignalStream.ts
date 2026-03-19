import { useState, useEffect, useCallback, useRef } from "react";
import type { Signal } from "@/api/types";
import { createSignalStream } from "@/api/client";

interface UseSignalStreamResult {
  signals: Signal[];
  isConnected: boolean;
  reconnect: () => void;
}

const MAX_SIGNALS = 100;

export function useSignalStream(): UseSignalStreamResult {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const sourceRef = useRef<EventSource | null>(null);
  const retryRef = useRef<number>();

  const connect = useCallback(() => {
    sourceRef.current?.close();
    clearTimeout(retryRef.current);

    const source = createSignalStream(
      (signal) => {
        setSignals((prev) => [signal, ...prev].slice(0, MAX_SIGNALS));
        setIsConnected(true);
      },
      () => {
        setIsConnected(false);
        retryRef.current = window.setTimeout(connect, 3000);
      }
    );

    source.onopen = () => setIsConnected(true);
    sourceRef.current = source;
  }, []);

  const reconnect = useCallback(() => {
    sourceRef.current?.close();
    clearTimeout(retryRef.current);
    connect();
  }, [connect]);

  useEffect(() => {
    connect();
    return () => {
      sourceRef.current?.close();
      clearTimeout(retryRef.current);
    };
  }, [connect]);

  return { signals, isConnected, reconnect };
}
