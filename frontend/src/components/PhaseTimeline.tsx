"use client";

import { PhaseEvent } from "@/hooks/useAgentSocket";

const PHASES = ["OBSERVE", "REASON", "PLAN", "DECIDE", "ACT", "VERIFY", "UPDATE"];

const PHASE_COLORS: Record<string, { bg: string; text: string; ring: string }> = {
  OBSERVE: { bg: "bg-blue-100", text: "text-blue-700", ring: "ring-blue-400" },
  REASON: { bg: "bg-purple-100", text: "text-purple-700", ring: "ring-purple-400" },
  PLAN: { bg: "bg-green-100", text: "text-green-700", ring: "ring-green-400" },
  DECIDE: { bg: "bg-orange-100", text: "text-orange-700", ring: "ring-orange-400" },
  ACT: { bg: "bg-red-100", text: "text-red-700", ring: "ring-red-400" },
  VERIFY: { bg: "bg-teal-100", text: "text-teal-700", ring: "ring-teal-400" },
  UPDATE: { bg: "bg-lime-100", text: "text-lime-700", ring: "ring-lime-400" },
};

const PHASE_ICONS: Record<string, string> = {
  OBSERVE: "🔍",
  REASON: "🧠",
  PLAN: "📋",
  DECIDE: "⚖️",
  ACT: "⚡",
  VERIFY: "✅",
  UPDATE: "📝",
};

interface Props {
  currentPhase: string | null;
  events: PhaseEvent[];
  iteration: number;
  isReviewing?: boolean;
}

export default function PhaseTimeline({ currentPhase, events, iteration, isReviewing = false }: Props) {
  const completedPhases = new Set(
    events.filter((e) => e.type === "phase_update" && e.phase).map((e) => e.phase!)
  );

  return (
    <div className="space-y-1">
      <div className="text-sm text-gray-500 mb-3">
        Iteration {iteration > 0 ? iteration : "—"}
      </div>
      {PHASES.map((phase, i) => {
        const isActive = currentPhase === phase;
        const isCompleted = completedPhases.has(phase) && !isActive;
        const colors = PHASE_COLORS[phase];

        return (
          <div key={phase} className="flex items-start gap-3">
            {/* Connector line */}
            <div className="flex flex-col items-center">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-sm
                  ${isActive ? `${colors.bg} ${colors.text} ring-2 ${colors.ring} animate-pulse` : ""}
                  ${isCompleted ? `${colors.bg} ${colors.text}` : ""}
                  ${!isActive && !isCompleted ? "bg-gray-100 text-gray-400" : ""}
                `}
              >
                {isCompleted ? "✓" : PHASE_ICONS[phase]}
              </div>
              {i < PHASES.length - 1 && (
                <div
                  className={`w-0.5 h-6 ${
                    isCompleted ? "bg-gray-300" : "bg-gray-100"
                  }`}
                />
              )}
            </div>

            {/* Phase label + data */}
            <div className="flex-1 pb-2">
              <div
                className={`text-sm font-medium ${
                  isActive ? colors.text : isCompleted ? "text-gray-700" : "text-gray-400"
                }`}
              >
                {phase}
              </div>
              {isActive && (
                <PhaseDetail
                  phase={phase}
                  events={events.filter((e) => e.phase === phase)}
                />
              )}
              {isCompleted && (
                <PhaseDetail
                  phase={phase}
                  events={events.filter((e) => e.phase === phase)}
                  collapsed
                />
              )}
              {phase === "VERIFY" && isReviewing && (
                <div className="text-xs mt-1 bg-amber-50 text-amber-700 rounded p-2 font-medium animate-pulse">
                  Awaiting your review...
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function PhaseDetail({
  phase,
  events,
  collapsed = false,
}: {
  phase: string;
  events: PhaseEvent[];
  collapsed?: boolean;
}) {
  const latest = events[events.length - 1];
  if (!latest?.data) return null;

  const data = latest.data;

  if (collapsed) {
    return <div className="text-xs text-gray-500 mt-0.5">{getSummary(phase, data)}</div>;
  }

  return (
    <div className="text-xs text-gray-600 mt-1 bg-gray-50 rounded p-2 max-h-48 overflow-y-auto">
      {getSummary(phase, data)}
    </div>
  );
}

function getSummary(phase: string, data: Record<string, unknown>): string {
  switch (phase) {
    case "OBSERVE": {
      const metrics = data.file_metrics as Array<Record<string, unknown>> | undefined;
      return metrics ? `Found ${metrics.length} files to analyze` : "Observing codebase...";
    }
    case "REASON": {
      const approach = data.approach as string | undefined;
      return approach || "Analyzing code patterns...";
    }
    case "PLAN": {
      const steps = data.steps as Array<unknown> | undefined;
      return steps ? `${steps.length} refactoring steps planned` : "Creating plan...";
    }
    case "DECIDE": {
      const approved = data.approved as boolean | undefined;
      const score = (data.risk_score as Record<string, unknown>)?.total_score;
      return `${approved ? "Approved" : "Blocked"} — risk score: ${score ?? "?"}`;
    }
    case "ACT": {
      if (Array.isArray(data)) {
        const done = data.filter((r) => r.status === "success").length;
        return `${done}/${data.length} steps executed`;
      }
      return "Executing changes...";
    }
    case "VERIFY": {
      const passed = data.tests_passed as boolean | undefined;
      const improved = data.improved as boolean | undefined;
      return `Tests ${passed ? "passed" : "failed"} — metrics ${improved ? "improved" : "unchanged"}`;
    }
    case "UPDATE":
      return "Memory and history updated";
    default:
      return JSON.stringify(data).slice(0, 120);
  }
}
