"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { startRefactor } from "@/lib/api";

export default function RefactorForm() {
  const router = useRouter();
  const [targetPath, setTargetPath] = useState("./sample_project");
  const [request, setRequest] = useState(
    "Refactor UserService to follow the Single Responsibility Principle. " +
      "Extract authentication, validation, persistence, and notification into separate classes."
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await startRefactor({ target_path: targetPath, request });
      router.push(`/session/${res.session_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start refactoring");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Target Project Path
        </label>
        <input
          type="text"
          value={targetPath}
          onChange={(e) => setTargetPath(e.target.value)}
          className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:ring-2 focus:ring-orange-400 focus:border-orange-400 outline-none"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Refactoring Request
        </label>
        <textarea
          value={request}
          onChange={(e) => setRequest(e.target.value)}
          rows={4}
          className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:ring-2 focus:ring-orange-400 focus:border-orange-400 outline-none resize-y"
        />
      </div>

      {error && (
        <div className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">
          {error}
        </div>
      )}

      <button
        type="submit"
        disabled={loading}
        className="w-full bg-gradient-to-r from-orange-500 to-yellow-500 text-white font-medium rounded-lg px-4 py-2.5 hover:from-orange-600 hover:to-yellow-600 disabled:opacity-50 disabled:cursor-not-allowed transition"
      >
        {loading ? "Starting..." : "Start Refactoring"}
      </button>
    </form>
  );
}
