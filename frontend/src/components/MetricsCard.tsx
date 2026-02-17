"use client";

import { Card, CardContent } from "@/components/ui/card";

interface Props {
  label: string;
  value: number | string;
  delta?: number;
  invertDelta?: boolean; // true = lower is better (complexity)
}

export default function MetricsCard({ label, value, delta, invertDelta = false }: Props) {
  let deltaColor = "text-muted-foreground";
  let deltaPrefix = "";
  if (delta !== undefined && delta !== 0) {
    const good = invertDelta ? delta < 0 : delta > 0;
    deltaColor = good ? "text-green-500" : "text-red-500";
    deltaPrefix = delta > 0 ? "+" : "";
  }

  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-xs text-muted-foreground uppercase tracking-wide">{label}</div>
        <div className="mt-1 flex items-baseline gap-2">
          <span className="text-2xl font-semibold text-foreground">{value}</span>
          {delta !== undefined && delta !== 0 && (
            <span className={`text-sm font-medium ${deltaColor}`}>
              {deltaPrefix}
              {delta}
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
