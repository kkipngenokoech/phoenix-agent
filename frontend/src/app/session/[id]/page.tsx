"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { useAgentSocket } from "@/hooks/useAgentSocket";
import { ReviewPayload, SessionDetail, getReview, getSession, submitReview } from "@/lib/api";
import DiffReview from "@/components/DiffReview";
import MetricsCard from "@/components/MetricsCard";
import PhaseStepper from "@/components/PhaseStepper";
import TerminalLog from "@/components/TerminalLog";
import Layout from "@/components/Layout";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Loader2, CheckCircle2, XCircle, ExternalLink, ShieldAlert, Cog, FileCode2, TestTube2, Search } from "lucide-react";
import { ActStepEvent } from "@/hooks/useAgentSocket";

export default function SessionPage() {
  const params = useParams();
  const sessionId = params.id as string;
  const { iterations, status, result, reviewPayload, approvalData, actStep, allEvents } =
    useAgentSocket(sessionId);

  const [fetchedReview, setFetchedReview] = useState<ReviewPayload | null>(null);
  const [reviewComplete, setReviewComplete] = useState(false);
  const [historicalResult, setHistoricalResult] = useState<Record<string, unknown> | null>(null);

  // Stable ref to track whether we've seen a review event (avoids allEvents in deps)
  const hasSeenReviewRef = useRef(false);
  if (allEvents.some((e) => e.type === "review_requested")) {
    hasSeenReviewRef.current = true;
  }

  useEffect(() => {
    if (reviewPayload || fetchedReview || !sessionId) return;
    if (!hasSeenReviewRef.current) return;

    getReview(sessionId)
      .then(setFetchedReview)
      .catch(() => {});
  }, [reviewPayload, fetchedReview, sessionId]);

  // Fetch session data from API immediately on mount.
  // If the session is already complete (viewing from history), show it right away.
  // If a live WebSocket result arrives later, it takes priority.
  useEffect(() => {
    if (!sessionId) return;
    getSession(sessionId)
      .then((data: SessionDetail) => {
        if (data.error) return;
        const sess = data.session;
        if (sess && (sess.status === "completed" || sess.status === "success" || sess.status === "failed")) {
          setHistoricalResult({
            status: sess.status === "completed" ? "success" : sess.status,
            session_id: sess.session_id,
            duration_seconds: sess.duration_seconds,
            original_files: data.original_files || {},
            refactored_files: data.refactored_files || {},
            metrics_before: data.metrics_before || {},
            metrics_after: data.metrics_after || {},
          });
        }
      })
      .catch(() => {});
  }, [sessionId]);

  const activeReview = reviewPayload || fetchedReview;
  const currentPhase = iterations[iterations.length - 1]?.currentPhase;

  return (
    <Layout>
      <div className="space-y-6 animate-fade-in">
        {/* Header */}
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              <span className="bg-gradient-to-r from-orange-400 to-amber-400 bg-clip-text text-transparent">
                Refactoring Session
              </span>
            </h1>
            <p className="text-xs text-muted-foreground/60 font-mono mt-1 break-all">
              {sessionId}
            </p>
          </div>
          <StatusBadge status={status} />
        </div>

        {/* Phase Stepper */}
        <PhaseStepper iterations={iterations} isDone={status === "done"} />

        {/* Main Content */}
        <div className="max-w-4xl mx-auto space-y-6">
          {/* Running state */}
          {!result && !historicalResult && !activeReview && !approvalData && (
            actStep ? (
              <ActProgressCard step={actStep} />
            ) : (
              <Card className="border-border/40">
                <CardContent className="flex flex-col items-center justify-center text-center py-16">
                  <div className="relative">
                    <Loader2 className="h-10 w-10 animate-spin text-phoenix" />
                    <div className="absolute inset-0 h-10 w-10 rounded-full bg-phoenix/10 animate-ping" />
                  </div>
                  <h3 className="text-lg font-semibold text-foreground mt-6">
                    Agent is Running
                  </h3>
                  {currentPhase && (
                    <p className="text-sm text-phoenix/80 font-mono mt-1">
                      {currentPhase}
                    </p>
                  )}
                  <p className="text-sm text-muted-foreground mt-2 max-w-sm">
                    The agent is analyzing and refactoring your code. Watch the
                    progress above and events below.
                  </p>
                </CardContent>
              </Card>
            )
          )}

          {/* Approval gate (high risk) */}
          {approvalData && !activeReview && !result && (
            <ApprovalCard sessionId={sessionId} data={approvalData} />
          )}

          {/* Review */}
          {activeReview && !reviewComplete && !result && (
            <DiffReview
              sessionId={sessionId}
              payload={activeReview}
              onComplete={() => setReviewComplete(true)}
            />
          )}

          {/* Result */}
          {(result || historicalResult) && <ResultCard result={(result || historicalResult)!} />}
        </div>

        {/* Terminal Log */}
        <TerminalLog events={allEvents} />
      </div>
    </Layout>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    connected: "bg-phoenix/15 text-phoenix border-phoenix/30",
    connecting: "bg-muted text-muted-foreground border-border",
    disconnected: "bg-muted text-muted-foreground border-border",
    reviewing: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    done: "bg-green-500/15 text-green-400 border-green-500/30",
  };

  return (
    <Badge
      variant="outline"
      className={`capitalize text-xs px-3 py-1 ${styles[status] || styles.disconnected}`}
    >
      <span
        className={`inline-block w-1.5 h-1.5 rounded-full mr-2 ${
          status === "connected"
            ? "bg-phoenix animate-pulse"
            : status === "done"
            ? "bg-green-400"
            : status === "reviewing"
            ? "bg-amber-400 animate-pulse"
            : "bg-muted-foreground"
        }`}
      />
      {status}
    </Badge>
  );
}

function ResultCard({ result }: { result: Record<string, unknown> }) {
  const status = result.status as string;
  const isSuccess = status === "success";
  const refactoredFiles = (result.refactored_files || {}) as Record<string, string>;
  const originalFiles = (result.original_files || {}) as Record<string, string>;
  const metricsBefore = (result.metrics_before || {}) as Record<string, number>;
  const metricsAfter = (result.metrics_after || {}) as Record<string, number>;
  const fileEntries = Object.entries(refactoredFiles);
  const [activeFile, setActiveFile] = useState(fileEntries[0]?.[0] || "");
  const [viewMode, setViewMode] = useState<"refactored" | "original">("refactored");
  const [copied, setCopied] = useState(false);

  const handleCopy = (content: string) => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Build metrics table data
  const allMetricFiles = Array.from(
    new Set([...Object.keys(metricsBefore), ...Object.keys(metricsAfter)])
  ).sort();
  const totalBefore = Object.values(metricsBefore).reduce((a, b) => a + b, 0);
  const totalAfter = Object.values(metricsAfter).reduce((a, b) => a + b, 0);
  const hasMetrics = allMetricFiles.length > 0;

  return (
    <div className="space-y-6">
      <Card
        className={
          isSuccess
            ? "border-phoenix/30 shadow-[0_0_20px_hsl(var(--phoenix)/0.08)]"
            : "border-red-500/30 shadow-[0_0_20px_rgba(239,68,68,0.08)]"
        }
      >
        <CardHeader>
          <CardTitle className="flex items-center gap-3">
            {isSuccess ? (
              <CheckCircle2 className="h-6 w-6 text-phoenix" />
            ) : (
              <XCircle className="h-6 w-6 text-red-400" />
            )}
            <span className={isSuccess ? "text-phoenix" : "text-red-400"}>
              {isSuccess ? "Refactoring Complete" : "Refactoring Failed"}
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {result.reason ? (
            <p className="text-sm text-muted-foreground mb-6">
              {String(result.reason)}
            </p>
          ) : null}

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {result.duration_seconds !== undefined ? (
              <MetricsCard
                label="Duration"
                value={`${(result.duration_seconds as number).toFixed(1)}s`}
              />
            ) : null}
            {result.branch ? (
              <MetricsCard label="Branch" value={String(result.branch)} />
            ) : null}
            {hasMetrics && (
              <>
                <MetricsCard label="Before" value={String(totalBefore)} />
                <MetricsCard label="After" value={String(totalAfter)} />
              </>
            )}
            {result.pr_url ? (
              <div className="col-span-2 flex items-center">
                <a
                  href={String(result.pr_url)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 text-sm font-semibold text-phoenix hover:text-phoenix/80 transition-colors"
                >
                  <ExternalLink className="h-4 w-4" />
                  View Pull Request
                </a>
              </div>
            ) : null}
          </div>
        </CardContent>
      </Card>

      {/* Complexity metrics table */}
      {isSuccess && hasMetrics && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Search className="h-5 w-5 text-phoenix" />
              Complexity Metrics
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-auto rounded-md border border-border">
              <table className="w-full text-xs font-mono">
                <thead>
                  <tr className="border-b border-border bg-muted/50">
                    <th className="text-left px-3 py-2 text-muted-foreground font-medium">File</th>
                    <th className="text-right px-3 py-2 text-muted-foreground font-medium">Before</th>
                    <th className="text-right px-3 py-2 text-muted-foreground font-medium">After</th>
                    <th className="text-right px-3 py-2 text-muted-foreground font-medium">Change</th>
                  </tr>
                </thead>
                <tbody>
                  {allMetricFiles.map((file) => {
                    const b = metricsBefore[file] ?? 0;
                    const a = metricsAfter[file] ?? 0;
                    const delta = a - b;
                    const shortName = file.split("/").pop() || file;
                    const isNew = !(file in metricsBefore);
                    return (
                      <tr key={file} className="border-b border-border/50 last:border-0">
                        <td className="px-3 py-2 text-foreground">
                          {shortName}
                          {isNew && (
                            <span className="ml-2 text-[10px] text-phoenix/70 bg-phoenix/10 px-1.5 py-0.5 rounded">
                              new
                            </span>
                          )}
                        </td>
                        <td className="text-right px-3 py-2 text-muted-foreground">
                          {file in metricsBefore ? b : "—"}
                        </td>
                        <td className="text-right px-3 py-2 text-muted-foreground">
                          {file in metricsAfter ? a : "—"}
                        </td>
                        <td
                          className={`text-right px-3 py-2 font-medium ${
                            delta < 0
                              ? "text-green-400"
                              : delta > 0
                              ? "text-red-400"
                              : "text-muted-foreground"
                          }`}
                        >
                          {isNew ? "new" : `${delta > 0 ? "+" : ""}${delta}`}
                        </td>
                      </tr>
                    );
                  })}
                  {/* Total row */}
                  <tr className="bg-muted/30 font-semibold">
                    <td className="px-3 py-2 text-foreground">Total</td>
                    <td className="text-right px-3 py-2 text-muted-foreground">{totalBefore}</td>
                    <td className="text-right px-3 py-2 text-muted-foreground">{totalAfter}</td>
                    <td
                      className={`text-right px-3 py-2 ${
                        totalAfter < totalBefore
                          ? "text-green-400"
                          : totalAfter > totalBefore
                          ? "text-red-400"
                          : "text-muted-foreground"
                      }`}
                    >
                      {totalAfter - totalBefore > 0 ? "+" : ""}
                      {totalAfter - totalBefore}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* GitHub-style file browser */}
      {isSuccess && fileEntries.length > 0 && (
        <Card className="overflow-hidden">
          <CardHeader className="pb-0">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base flex items-center gap-2">
                <FileCode2 className="h-5 w-5 text-phoenix" />
                Files
                <span className="text-xs text-muted-foreground font-normal ml-1">
                  {fileEntries.length} file{fileEntries.length !== 1 ? "s" : ""}
                </span>
              </CardTitle>
              {Object.keys(originalFiles).length > 0 && (
                <div className="flex rounded-md border border-border overflow-hidden text-xs">
                  <button
                    onClick={() => setViewMode("original")}
                    className={`px-3 py-1 transition-colors ${
                      viewMode === "original"
                        ? "bg-muted text-foreground font-medium"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    Original
                  </button>
                  <button
                    onClick={() => setViewMode("refactored")}
                    className={`px-3 py-1 transition-colors border-l border-border ${
                      viewMode === "refactored"
                        ? "bg-phoenix/15 text-phoenix font-medium"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    Refactored
                  </button>
                </div>
              )}
            </div>
          </CardHeader>
          <CardContent className="pt-4 px-0">
            <div className="flex min-h-[400px] border-t border-border">
              {/* File sidebar */}
              <div className="w-56 shrink-0 border-r border-border bg-muted/30 overflow-y-auto">
                {fileEntries.map(([name]) => {
                  const isNew = !(name in metricsBefore) && name !== "main.py";
                  return (
                    <button
                      key={name}
                      onClick={() => setActiveFile(name)}
                      className={`w-full text-left px-3 py-2 text-xs font-mono flex items-center gap-2 transition-colors border-l-2 ${
                        activeFile === name
                          ? "bg-phoenix/10 text-phoenix border-l-phoenix"
                          : "text-muted-foreground hover:text-foreground hover:bg-muted/50 border-l-transparent"
                      }`}
                    >
                      <FileCode2 className="h-3.5 w-3.5 shrink-0 opacity-60" />
                      <span className="truncate">{name}</span>
                      {isNew && (
                        <span className="ml-auto text-[9px] text-phoenix/70 bg-phoenix/10 px-1 py-0.5 rounded shrink-0">
                          new
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>

              {/* Code viewer */}
              <div className="flex-1 min-w-0">
                {activeFile ? (() => {
                  const activeContent = viewMode === "original"
                    ? (originalFiles[activeFile] || "")
                    : (refactoredFiles[activeFile] || "");
                  if (!activeContent) {
                    return (
                      <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
                        {viewMode === "original" ? "No original version available" : "Select a file to view"}
                      </div>
                    );
                  }
                  const lines = activeContent.split("\n");
                  return (
                    <div className="relative h-full flex flex-col">
                      {/* File header bar */}
                      <div className="flex items-center justify-between px-4 py-2 bg-muted/40 border-b border-border">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-mono text-foreground">{activeFile}</span>
                          {viewMode === "original" && (
                            <span className="text-[10px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                              original
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] text-muted-foreground">
                            {lines.length} lines
                          </span>
                          <Button
                            variant="outline"
                            size="sm"
                            className="h-6 text-[10px] px-2"
                            onClick={() => handleCopy(activeContent)}
                          >
                            {copied ? "Copied!" : "Copy"}
                          </Button>
                        </div>
                      </div>
                      {/* Code block */}
                      <pre className="overflow-auto flex-1 p-0 text-xs font-mono leading-relaxed">
                        {lines.map((line: string, i: number) => (
                          <div
                            key={i}
                            className="flex hover:bg-muted/30 transition-colors"
                          >
                            <span className="text-muted-foreground/40 select-none w-10 shrink-0 text-right pr-3 py-px border-r border-border/30 bg-muted/20">
                              {i + 1}
                            </span>
                            <span className="text-foreground pl-4 py-px whitespace-pre">
                              {line || " "}
                            </span>
                          </div>
                        ))}
                      </pre>
                    </div>
                  );
                })() : (
                  <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
                    Select a file to view
                  </div>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function ApprovalCard({
  sessionId,
  data,
}: {
  sessionId: string;
  data: Record<string, unknown>;
}) {
  const [submitting, setSubmitting] = useState(false);

  const handleDecision = async (approved: boolean) => {
    if (submitting) return;
    setSubmitting(true);
    try {
      await submitReview(sessionId, { approved });
    } catch {
      // Agent will handle timeout
    }
    // Don't reset submitting — the agent continues and the card should stay disabled
  };

  return (
    <Card className="border-amber-500/30 shadow-[0_0_20px_rgba(245,158,11,0.08)]">
      <CardHeader>
        <CardTitle className="flex items-center gap-3 text-amber-400">
          <ShieldAlert className="h-6 w-6" />
          High Risk — Approval Required
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">
          {String(data.reason || "This refactoring has a high risk score and requires your approval before proceeding.")}
        </p>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
          <MetricsCard label="Risk Score" value={Number(data.risk_score || 0).toFixed(1)} />
          <MetricsCard label="Plan Steps" value={data.plan_steps as number} />
          <MetricsCard label="Files Affected" value={data.files_affected as number} />
        </div>
        <div className="flex gap-3 pt-2">
          <Button
            variant="phoenix"
            disabled={submitting}
            onClick={() => handleDecision(true)}
          >
            {submitting ? "Submitting..." : "Approve & Proceed"}
          </Button>
          <Button
            variant="outline"
            disabled={submitting}
            onClick={() => handleDecision(false)}
          >
            Reject
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

const ACTION_META: Record<string, { icon: React.ReactNode; label: string; color: string }> = {
  modify_code: { icon: <FileCode2 className="h-4 w-4" />, label: "Modifying", color: "text-phoenix" },
  parse_code: { icon: <Search className="h-4 w-4" />, label: "Analyzing", color: "text-blue-400" },
  generate_tests: { icon: <TestTube2 className="h-4 w-4" />, label: "Generating Tests", color: "text-purple-400" },
  run_tests: { icon: <TestTube2 className="h-4 w-4" />, label: "Running Tests", color: "text-green-400" },
};

function ActProgressCard({ step }: { step: ActStepEvent }) {
  const meta = ACTION_META[step.action] || { icon: <Cog className="h-4 w-4" />, label: step.action, color: "text-muted-foreground" };
  const pct = Math.round((step.step_id / step.total_steps) * 100);
  const fileName = step.target_file?.split("/").pop();

  return (
    <Card className="border-phoenix/20">
      <CardContent className="py-6 space-y-4">
        {/* Progress bar */}
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span className="font-medium text-foreground">Executing Plan</span>
          <span>
            Step {step.step_id} of {step.total_steps}
          </span>
        </div>
        <div className="h-1.5 bg-muted rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-phoenix to-amber-400 rounded-full transition-all duration-500"
            style={{ width: `${pct}%` }}
          />
        </div>

        {/* Current step */}
        <div className="flex items-start gap-3 pt-1">
          <div className={`mt-0.5 ${meta.color}`}>
            {step.status === "running" ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : step.status === "success" ? (
              <CheckCircle2 className="h-4 w-4 text-green-400" />
            ) : (
              <XCircle className="h-4 w-4 text-red-400" />
            )}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className={`text-sm font-medium ${meta.color}`}>{meta.label}</span>
              {fileName && (
                <span className="text-xs font-mono text-muted-foreground/70 truncate">
                  {fileName}
                </span>
              )}
            </div>
            {step.description && (
              <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                {step.description}
              </p>
            )}
            {step.error && (
              <p className="text-xs text-red-400 mt-1 line-clamp-2">
                {step.error}
              </p>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
