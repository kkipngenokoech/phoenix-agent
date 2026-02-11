"use client";

import { TestResults as TestResultsType } from "@/lib/api";
import MetricsCard from "./MetricsCard";

interface Props {
  results: TestResultsType;
}

export default function TestResults({ results }: Props) {
  if (results.error) {
    return <div className="text-sm text-red-500">Test error: {results.error}</div>;
  }

  const s = results.summary;
  if (!s) return null;

  const allPassed = s.failed === 0;

  return (
    <div>
      <div
        className={`text-sm font-medium mb-3 ${
          allPassed ? "text-green-600" : "text-red-600"
        }`}
      >
        {allPassed ? "All tests passed" : `${s.failed} test(s) failed`}
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <MetricsCard label="Total" value={s.total} />
        <MetricsCard label="Passed" value={s.passed} />
        <MetricsCard label="Failed" value={s.failed} />
        <MetricsCard label="Duration" value={`${s.duration_seconds.toFixed(2)}s`} />
      </div>
    </div>
  );
}
