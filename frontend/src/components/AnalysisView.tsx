"use client";

import { useState } from "react";
import {
  AnalyzeRequest,
  InputType,
  runAnalysis,
  ParsedFile,
  TestResults as TestResultsType,
} from "@/lib/api";
import InputTabs from "./InputTabs";
import MetricsCard from "./MetricsCard";
import CodeSmellList from "./CodeSmellList";
import TestResults from "./TestResults";
import { Button } from "@/components/ui/button";

export default function AnalysisView() {
  const [inputType, setInputType] = useState<InputType>("local_path");
  const [targetPath, setTargetPath] = useState("./sample_project");
  const [pastedCode, setPastedCode] = useState("");
  const [githubUrl, setGithubUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [files, setFiles] = useState<ParsedFile[] | null>(null);
  const [testResults, setTestResults] = useState<TestResultsType | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleAnalyze = async () => {
    setLoading(true);
    setError(null);
    try {
      const req: AnalyzeRequest = { input_type: inputType };
      if (inputType === "local_path") req.target_path = targetPath;
      else if (inputType === "pasted_code") req.pasted_code = pastedCode;
      else if (inputType === "github_url") req.github_url = githubUrl;

      const res = await runAnalysis(req);
      setFiles(res.files);
      setTestResults(res.test_results);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <InputTabs
        inputType={inputType}
        onInputTypeChange={setInputType}
        targetPath={targetPath}
        onTargetPathChange={setTargetPath}
        pastedCode={pastedCode}
        onPastedCodeChange={setPastedCode}
        githubUrl={githubUrl}
        onGithubUrlChange={setGithubUrl}
      />

      <Button
        onClick={handleAnalyze}
        disabled={loading}
        variant="phoenix"
        className="w-full"
        size="lg"
      >
        {loading ? "Analyzing..." : "Run Analysis"}
      </Button>

      {error && (
        <div className="text-sm text-destructive bg-destructive/10 rounded-lg px-3 py-2">{error}</div>
      )}

      {testResults && (
        <div>
          <h3 className="text-lg font-semibold text-foreground mb-3">Test Results</h3>
          <TestResults results={testResults} />
        </div>
      )}

      {files && files.length > 0 && (
        <div>
          <h3 className="text-lg font-semibold text-foreground mb-3">AST Analysis</h3>
          <div className="space-y-4">
            {files.map((pf) => {
              const fname = pf.file_path.split("/").pop() || pf.file_path;
              return (
                <div
                  key={pf.file_path}
                  className="border border-border rounded-lg overflow-hidden"
                >
                  <div className="bg-secondary px-4 py-2 border-b border-border flex items-center justify-between">
                    <span className="font-medium text-sm text-foreground">{fname}</span>
                    <span className="text-xs text-muted-foreground">
                      complexity: {pf.metrics.cyclomatic_complexity} | smells:{" "}
                      {pf.code_smells.length}
                    </span>
                  </div>
                  <div className="p-4 space-y-4">
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                      <MetricsCard label="Lines" value={pf.metrics.lines_of_code} />
                      <MetricsCard label="Complexity" value={pf.metrics.cyclomatic_complexity} />
                      <MetricsCard label="Functions" value={pf.metrics.function_count} />
                      <MetricsCard label="Max Nesting" value={pf.metrics.max_nesting_depth} />
                    </div>
                    {pf.code_smells.length > 0 && (
                      <div>
                        <div className="text-sm font-medium text-foreground mb-2">
                          Code Smells
                        </div>
                        <CodeSmellList smells={pf.code_smells} />
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
