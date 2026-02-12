"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ReviewPayload, getReview, getWsUrl } from "@/lib/api";

export interface PhaseEvent {
  type:
    | "iteration_start"
    | "phase_update"
    | "completed"
    | "error"
    | "review_requested";
  session_id: string;
  iteration: number;
  phase: string | null;
  data: Record<string, unknown> | null;
  message?: string;
}

export type ConnectionStatus =
  | "disconnected"
  | "connecting"
  | "connected"
  | "done"
  | "reviewing";

export function useAgentSocket(sessionId: string | null) {
  const [events, setEvents] = useState<PhaseEvent[]>([]);
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const [currentPhase, setCurrentPhase] = useState<string | null>(null);
  const [iteration, setIteration] = useState(0);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [reviewPayload, setReviewPayload] = useState<ReviewPayload | null>(
    null
  );
  const wsRef = useRef<WebSocket | null>(null);
  const statusRef = useRef<ConnectionStatus>("disconnected");
  const retriesRef = useRef(0);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const MAX_RETRIES = 5;
  const RETRY_DELAY_MS = 2000;

  const connect = useCallback(() => {
    if (!sessionId) return;

    setStatus("connecting");
    statusRef.current = "connecting";
    const ws = new WebSocket(getWsUrl(sessionId));
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus("connected");
      statusRef.current = "connected";
      retriesRef.current = 0;
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
        } else if (event.type === "review_requested") {
          setReviewPayload(event.data as unknown as ReviewPayload);
          setStatus("reviewing");
          statusRef.current = "reviewing";
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
      if (
        statusRef.current === "done" ||
        statusRef.current === "reviewing"
      ) {
        return;
      }

      // Auto-reconnect if the session isn't finished yet
      if (retriesRef.current < MAX_RETRIES) {
        retriesRef.current += 1;
        setStatus("connecting");
        statusRef.current = "connecting";
        retryTimerRef.current = setTimeout(connect, RETRY_DELAY_MS);
      } else {
        setStatus("disconnected");
        statusRef.current = "disconnected";
      }
    };

    ws.onerror = () => {
      // onclose will fire after onerror — reconnect is handled there
    };
  }, [sessionId]);

  // Reconnect recovery: if we reconnect but the session is in review state,
  // fetch the review payload via REST
  useEffect(() => {
    if (!sessionId || reviewPayload || status !== "connected") return;

    const hasReviewEvent = events.some((e) => e.type === "review_requested");
    if (!hasReviewEvent) return;

    getReview(sessionId)
      .then((payload) => {
        setReviewPayload(payload);
        setStatus("reviewing");
        statusRef.current = "reviewing";
      })
      .catch(() => {
        // Review may have been resolved already
      });
  }, [sessionId, status, events, reviewPayload]);

  useEffect(() => {
    if (sessionId) connect();
    return () => {
      statusRef.current = "done"; // prevent reconnect on unmount
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
      wsRef.current?.close();
    };
  }, [sessionId, connect]);

  return { events, status, currentPhase, iteration, result, reviewPayload };
}
