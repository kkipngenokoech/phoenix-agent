"use client";

import { useEffect, useRef } from "react";
import { PhaseEvent } from "@/hooks/useAgentSocket";

interface Props {
  events: PhaseEvent[];
}

const typeColor: Record<string, string> = {
  phase_update: "text-orange-400",
  iteration_start: "text-muted-foreground",
  completed: "text-green-400",
  error: "text-red-400",
  review_requested: "text-amber-400",
};

export default function TerminalLog({ events }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events.length]);

  return (
    <div className="rounded-lg border border-border/60 bg-[hsl(240,10%,5%)] overflow-hidden">
      {/* Header bar */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-border/40 bg-[hsl(240,10%,6%)]">
        <div className="flex gap-1.5">
          <div className="w-2.5 h-2.5 rounded-full bg-red-500/60" />
          <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/60" />
          <div className="w-2.5 h-2.5 rounded-full bg-green-500/60" />
        </div>
        <span className="text-[11px] text-muted-foreground/70 font-mono ml-2">
          agent output
        </span>
      </div>

      {/* Log content */}
      <div
        ref={scrollRef}
        className="max-h-[240px] overflow-y-auto p-3 font-mono text-xs leading-relaxed"
      >
        {events.length === 0 ? (
          <div className="text-muted-foreground/50 flex items-center gap-2">
            <span className="text-phoenix/60">$</span>
            <span>Waiting for agent events...</span>
            <span className="inline-block w-1.5 h-3.5 bg-phoenix/60 animate-pulse" />
          </div>
        ) : (
          events.map((evt, i) => (
            <div key={i} className="flex gap-2 py-0.5 hover:bg-white/[0.02] rounded px-1 -mx-1">
              <span className="text-phoenix/50 shrink-0">$</span>
              <span className="text-muted-foreground/50 shrink-0 w-6 text-right">
                #{evt.iteration}
              </span>
              <span className={`shrink-0 w-36 ${typeColor[evt.type] || "text-muted-foreground"}`}>
                {evt.type}
                {evt.phase ? `/${evt.phase}` : ""}
              </span>
              <span className="text-muted-foreground/70 truncate">
                {evt.message || (evt.data ? JSON.stringify(evt.data).slice(0, 120) : "")}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
