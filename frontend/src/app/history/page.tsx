"use client";

import { useEffect, useState } from "react";
import Layout from "@/components/Layout";
import { CheckCircle, XCircle, Clock } from "lucide-react";

// This mirrors the SessionSummary schema from the backend
interface HistoryRecord {
  session_id: string;
  outcome: "success" | "failed" | "timeout" | "rejected";
  duration_seconds: number;
  files_modified: string[];
  pr_url: string | null;
  timestamp: string;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function getHistory(): Promise<HistoryRecord[]> {
  const res = await fetch(`${API_BASE_URL}/api/sessions`);
  if (!res.ok) {
    throw new Error("Failed to fetch session history");
  }
  return res.json();
}

const OutcomeBadge = ({ outcome }: { outcome: HistoryRecord["outcome"] }) => {
  const styles = {
    success: "bg-green-100 text-green-800",
    failed: "bg-red-100 text-red-800",
    timeout: "bg-yellow-100 text-yellow-800",
    rejected: "bg-amber-100 text-amber-800",
  };
  const icons = {
    success: <CheckCircle size={16} />,
    failed: <XCircle size={16} />,
    timeout: <Clock size={16} />,
    rejected: <XCircle size={16} />,
  };
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${
        styles[outcome] || "bg-gray-100 text-gray-800"
      }`}
    >
      {icons[outcome]}
      {outcome.charAt(0).toUpperCase() + outcome.slice(1)}
    </span>
  );
};


export default function HistoryPage() {
  const [history, setHistory] = useState<HistoryRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getHistory()
      .then((data) => {
        // Sort by most recent first
        const sortedData = data.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
        setHistory(sortedData);
      })
      .catch(() => {
        setError("Could not connect to the API server. Is it running?");
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  return (
    <Layout>
      <div className="mb-10">
        <h1 className="text-3xl font-bold text-gray-900">Session History</h1>
        <p className="mt-2 text-gray-600">
          Browse through past refactoring sessions.
        </p>
      </div>

      <div className="bg-white rounded-2xl border border-gray-200 shadow-lg shadow-gray-200/50 overflow-hidden">
        {loading && (
           <div className="p-12 text-center text-gray-500">Loading history...</div>
        )}
        {error && (
            <div className="p-12 text-center text-red-600 bg-red-50">{error}</div>
        )}
        {!loading && !error && history.length === 0 && (
            <div className="p-12 text-center text-gray-500">No history found.</div>
        )}
        {!loading && !error && history.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left">
                <tr>
                  <th className="px-6 py-3 font-semibold text-gray-600">Session ID</th>
                  <th className="px-6 py-3 font-semibold text-gray-600">Outcome</th>
                  <th className="px-6 py-3 font-semibold text-gray-600">Duration</th>
                  <th className="px-6 py-3 font-semibold text-gray-600">Modified Files</th>
                  <th className="px-6 py-3 font-semibold text-gray-600">Date</th>
                  <th className="px-6 py-3 font-semibold text-gray-600"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {history.map((record) => (
                  <tr key={record.session_id}>
                    <td className="px-6 py-4 whitespace-nowrap font-mono text-gray-700">{record.session_id}</td>
                    <td className="px-6 py-4 whitespace-nowrap"><OutcomeBadge outcome={record.outcome} /></td>
                    <td className="px-6 py-4 whitespace-nowrap text-gray-600">{record.duration_seconds.toFixed(1)}s</td>
                    <td className="px-6 py-4 whitespace-nowrap text-gray-600">{record.files_modified.length}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-gray-600">{new Date(record.timestamp).toLocaleString()}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-right">
                       <a href={`/session/${record.session_id}`} className="font-semibold text-orange-600 hover:text-orange-800">
                        View
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Layout>
  );
}
