"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useAgentSocket } from "@/hooks/useAgentSocket";
import PhaseTimeline from "@/components/PhaseTimeline";
import MetricsCard from "@/components/MetricsCard";

export default function SessionPage() {
  const params = useParams();
  const sessionId = params.id as string;
  const { events, status, currentPhase, iteration, result } =
    useAgentSocket(sessionId);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Session</h1>
          <p className="text-sm text-gray-500 font-mono mt-1">{sessionId}</p>
        </div>
        <StatusBadge status={status} />
      </div>

      <div className="grid lg:grid-cols-3 gap-8">
        {/* Phase Timeline */}
        <div className="lg:col-span-1 bg-white rounded-xl border border-gray-200 shadow-sm p-6">
          <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-4">
            Phase Progress
          </h2>
          <PhaseTimeline
            currentPhase={currentPhase}
            events={events}
            iteration={iteration}
          />
        </div>

        {/* Event Feed */}
        <div className="lg:col-span-2 space-y-6">
          {/* Result card (shown when done) */}
          {result ? <ResultCard result={result} /> : null}

          {/* Refactored code (shown on success) */}
          {result && result.refactored_files ? (
            <RefactoredCode
              files={result.refactored_files as Record<string, string>}
            />
          ) : null}

          {/* Live event log */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
            <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-4">
              Event Log
            </h2>
            <div className="space-y-2 max-h-[500px] overflow-y-auto">
              {events.length === 0 && (
                <p className="text-sm text-gray-400">
                  Waiting for agent events...
                </p>
              )}
              {events.map((evt, i) => (
                <div
                  key={i}
                  className="text-xs font-mono bg-gray-50 rounded px-3 py-2 flex gap-3"
                >
                  <span className="text-gray-400 shrink-0">
                    #{evt.iteration}
                  </span>
                  <span className="text-gray-600 shrink-0 w-28">
                    {evt.type}
                    {evt.phase ? ` / ${evt.phase}` : ""}
                  </span>
                  <span className="text-gray-500 truncate">
                    {evt.message ||
                      (evt.data
                        ? JSON.stringify(evt.data).slice(0, 100)
                        : "")}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    disconnected: "bg-gray-100 text-gray-600",
    connecting: "bg-yellow-100 text-yellow-700",
    connected: "bg-green-100 text-green-700",
    done: "bg-blue-100 text-blue-700",
  };
  return (
    <span
      className={`px-3 py-1 rounded-full text-xs font-medium ${
        styles[status] || styles.disconnected
      }`}
    >
      {status}
    </span>
  );
}

function ResultCard({ result }: { result: Record<string, unknown> }) {
  const status = result.status as string;
  const isSuccess = status === "success";

  return (
    <div
      className={`rounded-xl border p-6 ${
        isSuccess
          ? "bg-green-50 border-green-200"
          : "bg-red-50 border-red-200"
      }`}
    >
      <h2
        className={`text-lg font-semibold ${
          isSuccess ? "text-green-800" : "text-red-800"
        }`}
      >
        {isSuccess ? "Refactoring Successful" : `Refactoring ${status}`}
      </h2>

      {result.reason ? (
        <p className="text-sm mt-1 text-gray-600">{String(result.reason)}</p>
      ) : null}

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4">
        {result.duration_seconds !== undefined && (
          <MetricsCard
            label="Duration"
            value={`${(result.duration_seconds as number).toFixed(1)}s`}
          />
        )}
        {result.branch ? (
          <MetricsCard label="Branch" value={String(result.branch)} />
        ) : null}
        {result.pr_url ? (
          <div className="col-span-2 flex items-center">
            <a
              href={String(result.pr_url)}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-blue-600 hover:underline"
            >
              View Pull Request
            </a>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function RefactoredCode({ files }: { files: Record<string, string> }) {
  const fileNames = Object.keys(files);
  const [activeFile, setActiveFile] = useState(fileNames[0] || "");
  const [copied, setCopied] = useState(false);

  if (fileNames.length === 0) return null;

  const handleCopy = async () => {
    await navigator.clipboard.writeText(files[activeFile]);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      <div className="flex items-center justify-between border-b border-gray-200 bg-gray-50 px-4 py-2">
        <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
          Refactored Code
        </h2>
        <button
          onClick={handleCopy}
          className="text-xs px-3 py-1 rounded-md bg-gray-200 hover:bg-gray-300 text-gray-700 transition"
        >
          {copied ? "Copied!" : "Copy"}
        </button>
      </div>

      {/* File tabs */}
      {fileNames.length > 1 && (
        <div className="flex border-b border-gray-200 bg-gray-50 px-2 gap-1 overflow-x-auto">
          {fileNames.map((name) => (
            <button
              key={name}
              onClick={() => setActiveFile(name)}
              className={`px-3 py-1.5 text-xs font-mono whitespace-nowrap transition ${
                activeFile === name
                  ? "bg-white text-gray-900 border-b-2 border-orange-500"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              {name}
            </button>
          ))}
        </div>
      )}

      {/* Code display */}
      <div className="overflow-auto max-h-[600px]">
        <pre className="p-4 text-xs leading-relaxed">
          <code className="text-gray-800 font-mono whitespace-pre">
            {files[activeFile]}
          </code>
        </pre>
      </div>
    </div>
  );
}
