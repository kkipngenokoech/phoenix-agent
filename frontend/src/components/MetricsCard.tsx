"use client";

interface Props {
  label: string;
  value: number | string;
  delta?: number;
  invertDelta?: boolean; // true = lower is better (complexity)
}

export default function MetricsCard({ label, value, delta, invertDelta = false }: Props) {
  let deltaColor = "text-gray-400";
  let deltaPrefix = "";
  if (delta !== undefined && delta !== 0) {
    const good = invertDelta ? delta < 0 : delta > 0;
    deltaColor = good ? "text-green-600" : "text-red-600";
    deltaPrefix = delta > 0 ? "+" : "";
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 shadow-sm">
      <div className="text-xs text-gray-500 uppercase tracking-wide">{label}</div>
      <div className="mt-1 flex items-baseline gap-2">
        <span className="text-2xl font-semibold text-gray-900">{value}</span>
        {delta !== undefined && delta !== 0 && (
          <span className={`text-sm font-medium ${deltaColor}`}>
            {deltaPrefix}
            {delta}
          </span>
        )}
      </div>
    </div>
  );
}
