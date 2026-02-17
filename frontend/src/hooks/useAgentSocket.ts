"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ReviewPayload, getReview, getWsUrl } from "@/lib/api";

export interface PhaseEvent {
  type:
    | "iteration_start"
    | "phase_update"
    | "completed"
    | "error"
    | "review_requested"
    | "approval_requested"
    | "act_step"
    | "heartbeat";
  session_id: string;
  iteration: number;
  phase: string | null;
  data: Record<string, unknown> | null;
  message?: string;
}

export interface ActStepEvent {
  status: "running" | "success" | "failed";
  step_id: number;
  total_steps: number;
  action: string;
  description?: string;
  target_file?: string;
  error?: string;
}

export interface IterationState {
  iteration: number;
  events: PhaseEvent[];
  currentPhase: string | null;
}

export type ConnectionStatus =
  | "disconnected"
  | "connecting"
  | "connected"
  | "done"
  | "reviewing";

export function useAgentSocket(sessionId: string | null) {
  const [iterations, setIterations] = useState<IterationState[]>([]);
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [reviewPayload, setReviewPayload] = useState<ReviewPayload | null>(
    null
  );
  const [approvalData, setApprovalData] = useState<Record<string, unknown> | null>(null);
  const [actStep, setActStep] = useState<ActStepEvent | null>(null);
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
        const event = JSON.parse(msg.data) as PhaseEvent;

        // Ignore server heartbeats (keepalive pings)
        if (event.type === "heartbeat") return;

        setIterations((prev) => {
          const newIterations = [...prev];
          let iterationState = newIterations.find(
            (iter) => iter.iteration === event.iteration
          );

          if (!iterationState) {
            iterationState = {
              iteration: event.iteration,
              events: [],
              currentPhase: null,
            };
            newIterations.push(iterationState);
            newIterations.sort((a, b) => a.iteration - b.iteration);
          }

          iterationState.events.push(event);

          if (event.type === "phase_update" && event.phase) {
            iterationState.currentPhase = event.phase;
          }
          
          return newIterations;
        });

        if (event.type === "act_step") {
          setActStep(event.data as unknown as ActStepEvent);
        } else if (event.type === "approval_requested") {
          setApprovalData(event.data);
          setStatus("reviewing");
          statusRef.current = "reviewing";
        } else if (event.type === "phase_update") {
          // Agent moved to a new phase — clear transient UI states
          setApprovalData(null);
          setActStep(null);
          if (statusRef.current === "reviewing") {
            setStatus("connected");
            statusRef.current = "connected";
          }
        } else if (event.type === "review_requested") {
          setApprovalData(null);
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

  const allEvents = iterations.flatMap((iter) => iter.events);

  // Track whether we've already seen a review event (stable ref, no re-renders)
  const hasSeenReviewRef = useRef(false);
  if (allEvents.some((e) => e.type === "review_requested")) {
    hasSeenReviewRef.current = true;
  }

  // Reconnect recovery: if we reconnect but the session is in review state,
  // fetch the review payload via REST (runs only on status change)
  useEffect(() => {
    if (!sessionId || reviewPayload || status !== "connected") return;
    if (!hasSeenReviewRef.current) return;

    getReview(sessionId)
      .then((payload) => {
        setReviewPayload(payload);
        setStatus("reviewing");
        statusRef.current = "reviewing";
      })
      .catch(() => {
        // Review may have been resolved already
      });
  }, [sessionId, status, reviewPayload]);

  useEffect(() => {
    if (sessionId) connect();
    return () => {
      statusRef.current = "done"; // prevent reconnect on unmount
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
      wsRef.current?.close();
    };
  }, [sessionId, connect]);

  return { iterations, status, result, reviewPayload, approvalData, actStep, allEvents };
}
