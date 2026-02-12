"use client";

import { useState } from "react";
import { ReviewPayload, submitReview } from "@/lib/api";
import MetricsCard from "./MetricsCard";

interface Props {
  sessionId: string;
  payload: ReviewPayload;
  onComplete: (approved: boolean) => void;
}

export default function DiffReview({ sessionId, payload, onComplete }: Props) {
  const [activeFile, setActiveFile] = useState(0);
  const [viewMode, setViewMode] = useState<"split" | "unified">("split");
  const [submitting, setSubmitting] = useState(false);
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (approved: boolean) => {
    setSubmitting(true);
    setError(null);
    try {
      await submitReview(sessionId, { approved, comment });
      onComplete(approved);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit review");
    } finally {
      setSubmitting(false);
    }
  };

  const currentFile = payload.files[activeFile];

  return (
    <div className="space-y-6">
      {/* Summary banner */}
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-6">
        <h2 className="text-lg font-semibold text-amber-800">
          Review Required
        </h2>
        <p className="text-sm text-amber-700 mt-1">{payload.plan_summary}</p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4">
          <MetricsCard label="Files Changed" value={payload.files.length} />
          <MetricsCard
            label="Coverage"
            value={`${payload.coverage_pct.toFixed(1)}%`}
          />
          <MetricsCard
            label="Risk Score"
            value={payload.risk_score.toFixed(1)}
          />
          <MetricsCard
            label="Tests"
            value={
              payload.test_result?.summary?.passed !== undefined
                ? `${payload.test_result.summary.passed}/${payload.test_result.summary.total}`
                : "N/A"
            }
          />
        </div>
      </div>

      {/* Complexity before/after table */}
      <ComplexityTable
        before={payload.complexity_before}
        after={payload.complexity_after}
      />

      {/* File diff viewer */}
      {currentFile && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          {/* File tabs + view toggle */}
          <div className="flex items-center justify-between border-b border-gray-200 bg-gray-50 px-4 py-2">
            <div className="flex gap-1 overflow-x-auto">
              {payload.files.map((f, i) => (
                <button
                  key={f.file_path}
                  onClick={() => setActiveFile(i)}
                  className={`px-3 py-1.5 text-xs font-mono whitespace-nowrap transition rounded-t ${
                    i === activeFile
                      ? "bg-white text-gray-900 border-b-2 border-orange-500"
                      : "text-gray-500 hover:text-gray-700"
                  }`}
                >
                  {f.relative_path}
                  <span className="ml-2 text-green-600">+{f.lines_added}</span>
                  <span className="ml-1 text-red-600">-{f.lines_removed}</span>
                </button>
              ))}
            </div>
            <div className="flex gap-1 shrink-0 ml-4">
              <button
                onClick={() => setViewMode("split")}
                className={`px-2 py-1 text-xs rounded ${
                  viewMode === "split"
                    ? "bg-gray-200 text-gray-800 font-medium"
                    : "text-gray-500 hover:bg-gray-100"
                }`}
              >
                Split
              </button>
              <button
                onClick={() => setViewMode("unified")}
                className={`px-2 py-1 text-xs rounded ${
                  viewMode === "unified"
                    ? "bg-gray-200 text-gray-800 font-medium"
                    : "text-gray-500 hover:bg-gray-100"
                }`}
              >
                Unified
              </button>
            </div>
          </div>

          {/* Diff content */}
          <div className="overflow-auto max-h-[600px]">
            {viewMode === "unified" ? (
              <UnifiedDiff diff={currentFile.unified_diff} />
            ) : (
              <SplitDiff
                original={currentFile.original_content}
                modified={currentFile.modified_content}
              />
            )}
          </div>
        </div>
      )}

      {/* Comment + approve/reject */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder="Optional reviewer comment..."
          className="w-full border border-gray-300 rounded-lg p-3 text-sm mb-4 focus:outline-none focus:ring-2 focus:ring-orange-300"
          rows={3}
        />
        {error && (
          <p className="text-sm text-red-600 mb-3">{error}</p>
        )}
        <div className="flex gap-3 justify-end">
          <button
            onClick={() => handleSubmit(false)}
            disabled={submitting}
            className="px-4 py-2 rounded-lg border border-red-300 text-red-700 hover:bg-red-50 disabled:opacity-50 transition"
          >
            {submitting ? "Submitting..." : "Reject Changes"}
          </button>
          <button
            onClick={() => handleSubmit(true)}
            disabled={submitting}
            className="px-4 py-2 rounded-lg bg-green-600 text-white hover:bg-green-700 disabled:opacity-50 transition"
          >
            {submitting ? "Submitting..." : "Approve & Apply"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ComplexityTable({
  before,
  after,
}: {
  before: Record<string, number>;
  after: Record<string, number>;
}) {
  const files = Array.from(
    new Set([...Object.keys(before), ...Object.keys(after)])
  ).sort();

  if (files.length === 0) return null;

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
        <h3 className="text-sm font-semibold text-gray-700">
          Complexity Changes
        </h3>
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-100">
            <th className="text-left px-4 py-2 text-gray-500 font-medium">
              File
            </th>
            <th className="text-right px-4 py-2 text-gray-500 font-medium">
              Before
            </th>
            <th className="text-right px-4 py-2 text-gray-500 font-medium">
              After
            </th>
            <th className="text-right px-4 py-2 text-gray-500 font-medium">
              Change
            </th>
          </tr>
        </thead>
        <tbody>
          {files.map((f) => {
            const b = before[f] ?? 0;
            const a = after[f] ?? 0;
            const delta = a - b;
            const color =
              delta < 0
                ? "text-green-600"
                : delta > 0
                  ? "text-red-600"
                  : "text-gray-400";
            const sign = delta > 0 ? "+" : "";
            return (
              <tr key={f} className="border-b border-gray-50">
                <td className="px-4 py-2 font-mono text-xs text-gray-700">
                  {f.split("/").pop()}
                </td>
                <td className="text-right px-4 py-2 text-gray-600">{b}</td>
                <td className="text-right px-4 py-2 text-gray-600">{a}</td>
                <td className={`text-right px-4 py-2 font-medium ${color}`}>
                  {sign}
                  {delta}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function UnifiedDiff({ diff }: { diff: string }) {
  if (!diff) {
    return (
      <div className="p-4 text-sm text-gray-400">No changes detected</div>
    );
  }

  const lines = diff.split("\n");

  return (
    <pre className="text-xs leading-relaxed font-mono">
      {lines.map((line, i) => {
        let bg = "";
        let textColor = "text-gray-700";

        if (line.startsWith("+++") || line.startsWith("---")) {
          bg = "bg-gray-100";
          textColor = "text-gray-500 font-semibold";
        } else if (line.startsWith("@@")) {
          bg = "bg-blue-50";
          textColor = "text-blue-600";
        } else if (line.startsWith("+")) {
          bg = "bg-green-50";
          textColor = "text-green-800";
        } else if (line.startsWith("-")) {
          bg = "bg-red-50";
          textColor = "text-red-800";
        }

        return (
          <div key={i} className={`px-4 py-0.5 ${bg} ${textColor}`}>
            {line || " "}
          </div>
        );
      })}
    </pre>
  );
}

function SplitDiff({
  original,
  modified,
}: {
  original: string;
  modified: string;
}) {
  const origLines = original.split("\n");
  const modLines = modified.split("\n");
  const maxLines = Math.max(origLines.length, modLines.length);

  return (
    <div className="grid grid-cols-2 divide-x divide-gray-200">
      {/* Original (left) */}
      <div>
        <div className="px-3 py-1.5 bg-red-50 border-b border-gray-200 text-xs font-semibold text-red-700">
          Original
        </div>
        <pre className="text-xs leading-relaxed font-mono">
          {Array.from({ length: maxLines }, (_, i) => {
            const line = origLines[i] ?? "";
            const isRemoved =
              i < origLines.length &&
              (i >= modLines.length || origLines[i] !== modLines[i]);
            return (
              <div
                key={i}
                className={`px-3 py-0.5 flex ${isRemoved ? "bg-red-50" : ""}`}
              >
                <span className="text-gray-400 select-none w-8 shrink-0 text-right mr-3">
                  {i < origLines.length ? i + 1 : ""}
                </span>
                <span className={isRemoved ? "text-red-800" : "text-gray-700"}>
                  {line || " "}
                </span>
              </div>
            );
          })}
        </pre>
      </div>

      {/* Modified (right) */}
      <div>
        <div className="px-3 py-1.5 bg-green-50 border-b border-gray-200 text-xs font-semibold text-green-700">
          Modified
        </div>
        <pre className="text-xs leading-relaxed font-mono">
          {Array.from({ length: maxLines }, (_, i) => {
            const line = modLines[i] ?? "";
            const isAdded =
              i < modLines.length &&
              (i >= origLines.length || origLines[i] !== modLines[i]);
            return (
              <div
                key={i}
                className={`px-3 py-0.5 flex ${isAdded ? "bg-green-50" : ""}`}
              >
                <span className="text-gray-400 select-none w-8 shrink-0 text-right mr-3">
                  {i < modLines.length ? i + 1 : ""}
                </span>
                <span
                  className={isAdded ? "text-green-800" : "text-gray-700"}
                >
                  {line || " "}
                </span>
              </div>
            );
          })}
        </pre>
      </div>
    </div>
  );
}
