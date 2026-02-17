"use client";

import { IterationState } from "@/hooks/useAgentSocket";

const PHASES = ["OBSERVE", "REASON", "PLAN", "DECIDE", "ACT", "VERIFY", "UPDATE"];

interface Props {
  iterations: IterationState[];
  isDone: boolean;
}

export default function PhaseStepper({ iterations, isDone }: Props) {
  const allEvents = iterations.flatMap((iter) => iter.events);
  const completedPhases = new Set(
    allEvents
      .filter((e) => e.type === "phase_update" && e.phase)
      .map((e) => e.phase!)
  );

  const currentIteration = iterations[iterations.length - 1];
  const currentPhase = isDone ? null : currentIteration?.currentPhase;

  const getStatus = (phase: string) => {
    if (phase === currentPhase) return "active";
    if (completedPhases.has(phase)) return "completed";
    return "inactive";
  };

  // Find the index of the furthest completed or active phase for line coloring
  const activeIndex = PHASES.findIndex((p) => p === currentPhase);
  const furthestIndex = PHASES.reduce((max, phase, i) => {
    if (completedPhases.has(phase) || phase === currentPhase) return Math.max(max, i);
    return max;
  }, -1);

  return (
    <div className="w-full py-4">
      <div className="flex items-center justify-between max-w-2xl mx-auto px-4">
        {PHASES.map((phase, i) => {
          const status = getStatus(phase);
          const isLastPhase = i === PHASES.length - 1;

          return (
            <div key={phase} className="flex items-center flex-1 last:flex-none">
              {/* Node */}
              <div className="flex flex-col items-center gap-1.5">
                <div
                  className={`
                    w-8 h-8 rounded-full flex items-center justify-center text-[10px] font-bold transition-all duration-300
                    ${status === "active"
                      ? "bg-phoenix text-white shadow-[0_0_16px_hsl(var(--phoenix)/0.5)] animate-pulse"
                      : status === "completed"
                      ? "bg-phoenix/80 text-white"
                      : "bg-muted text-muted-foreground"
                    }
                  `}
                >
                  {status === "completed" ? (
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  ) : (
                    <span>{i + 1}</span>
                  )}
                </div>
                <span
                  className={`text-[10px] font-medium tracking-wide ${
                    status === "active"
                      ? "text-phoenix"
                      : status === "completed"
                      ? "text-phoenix/70"
                      : "text-muted-foreground/60"
                  }`}
                >
                  {phase.charAt(0) + phase.slice(1).toLowerCase()}
                </span>
              </div>

              {/* Connecting line */}
              {!isLastPhase && (
                <div
                  className={`flex-1 h-px mx-1.5 transition-colors duration-300 ${
                    i < furthestIndex
                      ? "bg-phoenix/50"
                      : i === activeIndex
                      ? "bg-phoenix/30"
                      : "bg-border"
                  }`}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
