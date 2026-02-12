"use client";

import { InputType } from "@/lib/api";

const TABS: { key: InputType; label: string }[] = [
  { key: "local_path", label: "Local Path" },
  { key: "pasted_code", label: "Paste Code" },
  { key: "github_url", label: "GitHub URL" },
];

interface InputTabsProps {
  inputType: InputType;
  onInputTypeChange: (type: InputType) => void;
  targetPath: string;
  onTargetPathChange: (v: string) => void;
  pastedCode: string;
  onPastedCodeChange: (v: string) => void;
  githubUrl: string;
  onGithubUrlChange: (v: string) => void;
}

export default function InputTabs({
  inputType,
  onInputTypeChange,
  targetPath,
  onTargetPathChange,
  pastedCode,
  onPastedCodeChange,
  githubUrl,
  onGithubUrlChange,
}: InputTabsProps) {
  return (
    <div className="space-y-3">
      {/* Tab bar */}
      <div className="flex border-b border-gray-200">
        {TABS.map((tab) => {
          const active = inputType === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => onInputTypeChange(tab.key)}
              className={`px-4 py-2 text-sm font-medium transition -mb-px ${
                active
                  ? "text-orange-600 border-b-2 border-orange-500"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab panels */}
      {inputType === "local_path" && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Project Directory
          </label>
          <input
            type="text"
            value={targetPath}
            onChange={(e) => onTargetPathChange(e.target.value)}
            placeholder="./sample_project"
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:ring-2 focus:ring-orange-400 focus:border-orange-400 outline-none"
          />
        </div>
      )}

      {inputType === "pasted_code" && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Python Code
          </label>
          <textarea
            value={pastedCode}
            onChange={(e) => onPastedCodeChange(e.target.value)}
            rows={12}
            placeholder="Paste your Python code here..."
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono focus:ring-2 focus:ring-orange-400 focus:border-orange-400 outline-none resize-y"
          />
        </div>
      )}

      {inputType === "github_url" && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            GitHub URL
          </label>
          <input
            type="text"
            value={githubUrl}
            onChange={(e) => onGithubUrlChange(e.target.value)}
            placeholder="https://github.com/owner/repo"
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:ring-2 focus:ring-orange-400 focus:border-orange-400 outline-none"
          />
          <p className="text-xs text-gray-400 mt-1">
            Supports repo URLs, branch paths, and directory URLs
          </p>
        </div>
      )}
    </div>
  );
}
