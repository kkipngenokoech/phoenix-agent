"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getWsUrl } from "@/lib/api";

export interface PhaseEvent {
  type: "iteration_start" | "phase_update" | "completed" | "error";
  session_id: string;
  iteration: number;
  phase: string | null;
  data: Record<string, unknown> | null;
  message?: string;
}

export type ConnectionStatus = "disconnected" | "connecting" | "connected" | "done";

export function useAgentSocket(sessionId: string | null) {
  const [events, setEvents] = useState<PhaseEvent[]>([]);
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const [currentPhase, setCurrentPhase] = useState<string | null>(null);
  const [iteration, setIteration] = useState(0);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const statusRef = useRef<ConnectionStatus>("disconnected");

  const connect = useCallback(() => {
    if (!sessionId) return;

    setStatus("connecting");
    statusRef.current = "connecting";
    const ws = new WebSocket(getWsUrl(sessionId));
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus("connected");
      statusRef.current = "connected";
    };

    ws.onmessage = (msg) => {
      try {
        const event = JSON.parse(msg.data);

        // Ignore server heartbeats (keepalive pings)
        if (event.type === "heartbeat") return;

        setEvents((prev) => [...prev, event as PhaseEvent]);

        if (event.type === "iteration_start") {
          setIteration(event.iteration);
        } else if (event.type === "phase_update" && event.phase) {
          setCurrentPhase(event.phase);
        } else if (event.type === "completed") {
          setResult(event.data);
          setStatus("done");
          statusRef.current = "done";
        } else if (event.type === "error") {
          // Keep listening — errors don't always mean the session is over
        }
      } catch {
        // Ignore non-JSON messages
      }
    };

    ws.onclose = () => {
      if (statusRef.current !== "done") {
        setStatus("disconnected");
        statusRef.current = "disconnected";
      }
    };

    ws.onerror = () => {
      setStatus("disconnected");
      statusRef.current = "disconnected";
    };
  }, [sessionId]);

  useEffect(() => {
    if (sessionId) connect();
    return () => {
      wsRef.current?.close();
    };
  }, [sessionId, connect]);

  return { events, status, currentPhase, iteration, result };
}
