"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getSessions, SessionSummary } from "@/lib/api";

export default function HistoryPage() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getSessions();
      setSessions(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load history");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Refactoring History</h1>
        <button
          onClick={load}
          disabled={loading}
          className="text-sm bg-gray-900 text-white rounded-lg px-4 py-2 hover:bg-gray-800 disabled:opacity-50 transition"
        >
          {loading ? "Loading..." : "Refresh"}
        </button>
      </div>

      {error && (
        <div className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">
          {error}
        </div>
      )}

      {sessions.length === 0 && !loading && !error && (
        <div className="text-center py-16 text-gray-400">
          <p className="text-lg">No refactoring sessions yet</p>
          <p className="text-sm mt-1">
            Start a refactoring from the{" "}
            <Link href="/" className="text-orange-500 hover:underline">
              Dashboard
            </Link>
          </p>
        </div>
      )}

      <div className="space-y-3">
        {sessions.map((s) => {
          const isSuccess = s.outcome === "success";
          return (
            <Link
              key={s.session_id}
              href={`/session/${s.session_id}`}
              className="block bg-white border border-gray-200 rounded-lg p-4 hover:border-orange-300 hover:shadow-sm transition"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span
                    className={`w-2 h-2 rounded-full ${
                      isSuccess ? "bg-green-500" : "bg-red-500"
                    }`}
                  />
                  <span className="text-sm font-mono text-gray-800">
                    {s.session_id}
                  </span>
                  <span
                    className={`text-xs px-2 py-0.5 rounded ${
                      isSuccess
                        ? "bg-green-100 text-green-700"
                        : "bg-red-100 text-red-700"
                    }`}
                  >
                    {s.outcome}
                  </span>
                </div>
                <div className="text-xs text-gray-400">
                  {s.duration_seconds.toFixed(1)}s
                  {s.timestamp && (
                    <span className="ml-3">
                      {new Date(s.timestamp).toLocaleDateString()}
                    </span>
                  )}
                </div>
              </div>
              {s.files_modified.length > 0 && (
                <div className="mt-2 text-xs text-gray-500">
                  Modified: {s.files_modified.join(", ")}
                </div>
              )}
              {s.pr_url && (
                <div className="mt-1 text-xs text-blue-500">{s.pr_url}</div>
              )}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
