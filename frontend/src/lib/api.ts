const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type InputType = "local_path" | "pasted_code" | "github_url";

export interface RefactorRequest {
  input_type: InputType;
  target_path?: string;
  pasted_code?: string;
  pasted_files?: Record<string, string>;
  github_url?: string;
  request: string;
}

export interface RefactorResponse {
  session_id: string;
  status: string;
}

export interface AnalyzeRequest {
  input_type: InputType;
  target_path?: string;
  pasted_code?: string;
  pasted_files?: Record<string, string>;
  github_url?: string;
}

export interface AnalyzeResponse {
  files: ParsedFile[];
  test_results: TestResults | null;
}

export interface ParsedFile {
  file_path: string;
  metrics: {
    lines_of_code: number;
    cyclomatic_complexity: number;
    function_count: number;
    class_count: number;
    max_nesting_depth: number;
  };
  code_smells: CodeSmell[];
}

export interface CodeSmell {
  type: string;
  location: { start_line?: number; end_line?: number };
  severity: "low" | "medium" | "high";
  description: string;
}

export interface TestResults {
  summary?: {
    total: number;
    passed: number;
    failed: number;
    skipped: number;
    duration_seconds: number;
  };
  error?: string;
}

export interface SessionSummary {
  session_id: string;
  outcome: string;
  duration_seconds: number;
  files_modified: string[];
  pr_url: string | null;
  timestamp: string | null;
}

// ---------------------------------------------------------------------------
// Review (human-in-the-loop)
// ---------------------------------------------------------------------------

export interface FileDiff {
  file_path: string;
  relative_path: string;
  original_content: string;
  modified_content: string;
  unified_diff: string;
  lines_added: number;
  lines_removed: number;
}

export interface ReviewPayload {
  session_id: string;
  files: FileDiff[];
  test_result: TestResults | null;
  coverage_pct: number;
  complexity_before: Record<string, number>;
  complexity_after: Record<string, number>;
  risk_score: number;
  plan_summary: string;
}

export interface ReviewVerdict {
  approved: boolean;
  comment?: string;
}

// ---------------------------------------------------------------------------
// API Functions
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Directory Browser
// ---------------------------------------------------------------------------

export interface BrowseEntry {
  name: string;
  path: string;
  has_children: boolean;
}

export interface BrowseResult {
  current: string;
  parent: string | null;
  entries: BrowseEntry[];
  error?: string;
}

export async function browseFolders(path?: string): Promise<BrowseResult> {
  const params = path ? `?path=${encodeURIComponent(path)}` : "";
  const res = await fetch(`${API_BASE}/api/browse${params}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Refactoring
// ---------------------------------------------------------------------------

export async function startRefactor(req: RefactorRequest): Promise<RefactorResponse> {
  const res = await fetch(`${API_BASE}/api/refactor`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function runAnalysis(req: AnalyzeRequest): Promise<AnalyzeResponse> {
  const res = await fetch(`${API_BASE}/api/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getSessions(): Promise<SessionSummary[]> {
  const res = await fetch(`${API_BASE}/api/sessions`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export interface SessionDetail {
  session?: {
    session_id: string;
    status: string;
    duration_seconds?: number;
    [key: string]: unknown;
  };
  iterations?: unknown[];
  original_files?: Record<string, string>;
  refactored_files?: Record<string, string>;
  metrics_before?: Record<string, number>;
  metrics_after?: Record<string, number>;
  error?: string;
}

export async function getSession(id: string): Promise<SessionDetail> {
  const res = await fetch(`${API_BASE}/api/sessions/${id}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function submitReview(
  sessionId: string,
  verdict: ReviewVerdict
): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(verdict),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getReview(sessionId: string): Promise<ReviewPayload> {
  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/review`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export function getWsUrl(sessionId: string): string {
  const base = API_BASE.replace(/^http/, "ws");
  return `${base}/ws/${sessionId}`;
}
