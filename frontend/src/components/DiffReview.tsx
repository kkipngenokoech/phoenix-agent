"use client";

import { useState } from "react";
import { ReviewPayload, submitReview } from "@/lib/api";
import MetricsCard from "./MetricsCard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";


interface Props {
  sessionId: string;
  payload: ReviewPayload;
  onComplete: (approved: boolean) => void;
}

export default function DiffReview({ sessionId, payload, onComplete }: Props) {
  const [activeFile, setActiveFile] = useState(payload.files[0]?.file_path || "");
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

  const currentFile = payload.files.find(f => f.file_path === activeFile);

  return (
    <div className="space-y-8">
      {/* Staging notice */}
      <div className="rounded-lg border border-border bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
        Your original files are untouched. These changes are staged in a temporary copy — they will only be applied to your project when you approve.
      </div>

      {/* Summary banner */}
      <Card className="bg-phoenix/5 border-phoenix/20">
        <CardHeader>
          <CardTitle className="text-phoenix">Review Proposed Changes</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-phoenix/70 mt-1">{payload.plan_summary}</p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-6">
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
        </CardContent>
      </Card>

      {/* Complexity before/after table */}
      <ComplexityTable
        before={payload.complexity_before}
        after={payload.complexity_after}
      />

      {/* File diff viewer */}
      {currentFile && (
        <Card>
          <Tabs defaultValue={payload.files[0]?.file_path || ""}>
            <TabsList>
              {payload.files.map((f) => (
                <TabsTrigger key={f.file_path} value={f.file_path} onClick={() => setActiveFile(f.file_path)}>
                  {f.relative_path}
                  <span className="ml-2 text-green-500 font-mono">+{f.lines_added}</span>
                  <span className="ml-1 text-red-500 font-mono">-{f.lines_removed}</span>
                </TabsTrigger>
              ))}
            </TabsList>
            <div className="flex items-center justify-end p-2">
                <Tabs value={viewMode} onValueChange={(v) => setViewMode(v as any)}>
                    <TabsList>
                        <TabsTrigger value="split">Split</TabsTrigger>
                        <TabsTrigger value="unified">Unified</TabsTrigger>
                    </TabsList>
                </Tabs>
            </div>
            
            {payload.files.map(f => (
                 <TabsContent key={f.file_path} value={f.file_path}>
                    <div className="overflow-auto max-h-[600px]">
                      {viewMode === "unified" ? (
                        <UnifiedDiff diff={f.unified_diff} />
                      ) : (
                        <SplitDiff
                          original={f.original_content}
                          modified={f.modified_content}
                        />
                      )}
                    </div>
                </TabsContent>
            ))}
          </Tabs>
        </Card>
      )}

      {/* Comment + approve/reject */}
      <Card>
        <CardContent className="pt-6">
          <div className="space-y-2">
            <Label htmlFor="review-comment">Add a Comment (Optional)</Label>
            <Textarea
              id="review-comment"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="e.g., Looks good, but please add documentation for the new service..."
              rows={3}
            />
          </div>
          {error && (
            <p className="text-sm text-destructive mt-3 font-medium">Error: {error}</p>
          )}
          <div className="flex gap-4 justify-end mt-4">
            <Button
              onClick={() => handleSubmit(false)}
              disabled={submitting}
              variant="outline"
            >
              {submitting ? "Submitting..." : "Reject Changes"}
            </Button>
            <Button
              onClick={() => handleSubmit(true)}
              disabled={submitting}
              variant="phoenix"
            >
              {submitting ? "Submitting..." : "Approve & Apply"}
            </Button>
          </div>
        </CardContent>
      </Card>
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
    <Card>
      <CardHeader>
        <CardTitle>Complexity Changes</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-secondary">
                <th className="text-left px-6 py-3 text-muted-foreground font-semibold text-xs uppercase tracking-wider">
                  File
                </th>
                <th className="text-right px-6 py-3 text-muted-foreground font-semibold text-xs uppercase tracking-wider">
                  Before
                </th>
                <th className="text-right px-6 py-3 text-muted-foreground font-semibold text-xs uppercase tracking-wider">
                  After
                </th>
                <th className="text-right px-6 py-3 text-muted-foreground font-semibold text-xs uppercase tracking-wider">
                  Change
                </th>
              </tr>
            </thead>
            <tbody>
              {files.map((f, i) => {
                const b = before[f] ?? 0;
                const a = after[f] ?? 0;
                const delta = a - b;
                const color =
                  delta < 0
                    ? "text-green-500"
                    : delta > 0
                    ? "text-red-500"
                    : "text-muted-foreground";
                const sign = delta > 0 ? "+" : "";
                return (
                  <tr key={f} className={i < files.length - 1 ? "border-b border-border" : ""}>
                    <td className="px-6 py-3 font-mono text-xs text-foreground whitespace-nowrap">
                      {f.split("/").pop()}
                    </td>
                    <td className="text-right px-6 py-3 text-muted-foreground font-mono text-xs">{b}</td>
                    <td className="text-right px-6 py-3 text-muted-foreground font-mono text-xs">{a}</td>
                    <td className={`text-right px-6 py-3 font-medium font-mono text-xs ${color}`}>
                      {sign}
                      {delta}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

function UnifiedDiff({ diff }: { diff: string }) {
  if (!diff) {
    return (
      <div className="p-4 text-sm text-muted-foreground">No changes detected</div>
    );
  }
  const lines = diff.split("\n");
  return (
    <pre className="text-xs leading-relaxed font-mono">
      {lines.map((line, i) => {
        let bg = "bg-transparent";
        let textColor = "text-foreground";
        if (line.startsWith("+++") || line.startsWith("---")) {
          bg = "bg-secondary";
          textColor = "text-muted-foreground font-semibold";
        } else if (line.startsWith("@@")) {
          bg = "bg-blue-600/10";
          textColor = "text-blue-400";
        } else if (line.startsWith("+")) {
          bg = "bg-green-600/10";
          textColor = "text-green-400";
        } else if (line.startsWith("-")) {
          bg = "bg-red-600/10";
          textColor = "text-red-400";
        }
        return (
          <div key={i} className={`px-6 py-0.5 ${bg} ${textColor} flex`}>
            <span className="w-10 shrink-0 select-none text-muted-foreground">
              {line.startsWith('-') ? '-' : line.startsWith('+') ? '+' : ' '}
            </span>
            <span>{line.slice(1) || " "}</span>
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
  // This is a simplified split view logic for brevity.
  // A real implementation would use a proper diffing library for accuracy.
  const origLines = original.split("\n");
  const modLines = modified.split("\n");
  const maxLines = Math.max(origLines.length, modLines.length);

  return (
    <div className="grid grid-cols-2 text-xs font-mono leading-relaxed">
      {/* Original (left) */}
      <div className="divide-y divide-border">
        <div className="px-4 py-2 bg-red-600/10 border-b border-border font-semibold text-red-400">
          Before
        </div>
        {Array.from({ length: maxLines }).map((_, i) => {
          const line = origLines[i];
          const isRemoved = line !== undefined && line !== modLines[i];
          return (
            <div key={`orig-${i}`} className={`px-4 py-0.5 flex ${isRemoved ? "bg-red-600/20" : ""}`}>
              <span className="text-muted-foreground select-none w-8 shrink-0 text-right mr-4">{i + 1}</span>
              <span className={isRemoved ? "text-red-400" : "text-foreground"}>{line ?? " "}</span>
            </div>
          );
        })}
      </div>

      {/* Modified (right) */}
      <div className="divide-y divide-border border-l border-border">
        <div className="px-4 py-2 bg-green-600/10 border-b border-border font-semibold text-green-400">
          After
        </div>
        {Array.from({ length: maxLines }).map((_, i) => {
          const line = modLines[i];
           const isAdded = line !== undefined && line !== origLines[i];
          return (
            <div key={`mod-${i}`} className={`px-4 py-0.5 flex ${isAdded ? "bg-green-600/20" : ""}`}>
              <span className="text-muted-foreground select-none w-8 shrink-0 text-right mr-4">{i + 1}</span>
              <span className={isAdded ? "text-green-400" : "text-foreground"}>{line ?? " "}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
