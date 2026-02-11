"use client";

import { CodeSmell } from "@/lib/api";

const SEVERITY_BADGE: Record<string, { bg: string; text: string }> = {
  high: { bg: "bg-red-100", text: "text-red-700" },
  medium: { bg: "bg-yellow-100", text: "text-yellow-700" },
  low: { bg: "bg-green-100", text: "text-green-700" },
};

interface Props {
  smells: CodeSmell[];
}

export default function CodeSmellList({ smells }: Props) {
  if (smells.length === 0) {
    return <div className="text-sm text-gray-400">No code smells detected</div>;
  }

  return (
    <ul className="space-y-2">
      {smells.map((smell, i) => {
        const badge = SEVERITY_BADGE[smell.severity] || SEVERITY_BADGE.low;
        return (
          <li key={i} className="flex items-start gap-2 text-sm">
            <span
              className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${badge.bg} ${badge.text}`}
            >
              {smell.severity}
            </span>
            <div>
              <span className="font-medium text-gray-800">{smell.type}</span>
              {smell.location?.start_line && (
                <span className="text-gray-400 ml-1">:L{smell.location.start_line}</span>
              )}
              {smell.description && (
                <p className="text-gray-500 mt-0.5">{smell.description}</p>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
