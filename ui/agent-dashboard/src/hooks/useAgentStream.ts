import { useCallback, useEffect, useRef, useState } from "react";
import type { AgentEvent, ConnectionStatus } from "../types";

const MAX_EVENTS = 200;
const RECONNECT_DELAY_MS = 3000;

interface UseAgentStreamOptions {
  agentName?: string;
  eventType?: string;
  enabled?: boolean;
}

export function useAgentStream(options: UseAgentStreamOptions = {}) {
  const { agentName, eventType, enabled = true } = options;
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = useCallback(() => {
    if (!enabled) return;

    const baseUrl = import.meta.env.VITE_API_URL || "/api";
    const params = new URLSearchParams();
    if (agentName) params.set("agent_name", agentName);
    if (eventType) params.set("event_type", eventType);
    const qs = params.toString();
    const url = `${baseUrl}/events/stream${qs ? `?${qs}` : ""}`;

    setStatus("connecting");
    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.onopen = () => setStatus("connected");

    es.onmessage = (msg) => {
      try {
        const event: AgentEvent = JSON.parse(msg.data);
        setEvents((prev) => {
          const next = [event, ...prev];
          return next.length > MAX_EVENTS ? next.slice(0, MAX_EVENTS) : next;
        });
      } catch {
        // skip invalid messages
      }
    };

    // Listen for typed events
    for (const type of ["signal", "reasoning", "tool_call", "decision"]) {
      es.addEventListener(type, (msg) => {
        try {
          const event: AgentEvent = JSON.parse((msg as MessageEvent).data);
          setEvents((prev) => {
            const next = [event, ...prev];
            return next.length > MAX_EVENTS ? next.slice(0, MAX_EVENTS) : next;
          });
        } catch {
          // skip
        }
      });
    }

    es.onerror = () => {
      setStatus("disconnected");
      es.close();
      reconnectTimerRef.current = setTimeout(connect, RECONNECT_DELAY_MS);
    };
  }, [agentName, eventType, enabled]);

  useEffect(() => {
    connect();
    return () => {
      eventSourceRef.current?.close();
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
    };
  }, [connect]);

  const clearEvents = useCallback(() => setEvents([]), []);

  return { events, status, clearEvents };
}
