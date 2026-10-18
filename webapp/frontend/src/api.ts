const BASE = "/api";
export const API_BASE = BASE;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface Job {
  job_id: string;
  status: string;
  description: string;
  created_at: string;
  updated_at: string;
  has_proof: boolean;
}

export interface Attempt {
  agent_index: number;
  turn: number;
  compiler_output: string;
  llm_model: string;
  success: boolean;
  created_at: string;
}

export interface JobDetail extends Job {
  lean_source: string;
  proof: string | null;
  attempts: Attempt[];
}

export interface Problem {
  id: string;
  title: string;
  statement: string;
  lean_source: string | null;
  source: string;
  difficulty: string;
  tags: string;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface SystemStatus {
  server: string;
  version: string;
  checked_at: string;
  lean_workspace: {
    ok: boolean | null;
    message: string;
    checked_at: string | null;
  };
  database: {
    path: string;
    exists: boolean;
    size_bytes: number | null;
  };
  config: {
    parallel_agents: number;
    max_turns: number;
    max_concurrent_compiles: number;
    escalate_to_tier2_after: number;
    escalate_to_tier3_after: number;
    tier1_model: string;
    tier2_model: string;
    tier3_model: string;
  };
  jobs: {
    total: number;
    running: number;
    complete: number;
    failed: number;
    cancelled: number;
    interrupted: number;
    live_tasks: number;
  };
}

export interface HealthResponse {
  status: string;
  server: string;
  version: string;
  lean_workspace_ok: boolean | null;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${path} returned ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Health / status
// ---------------------------------------------------------------------------

export async function fetchHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/health");
}

export async function fetchStatus(): Promise<SystemStatus> {
  return apiFetch<SystemStatus>("/status");
}

// ---------------------------------------------------------------------------
// Docs
// ---------------------------------------------------------------------------

export async function fetchDoc(name: string): Promise<string> {
  const res = await fetch(`${BASE}/docs/${encodeURIComponent(name)}`);
  if (!res.ok) throw new Error(`Doc '${name}' not found (${res.status})`);
  return res.text();
}

// ---------------------------------------------------------------------------
// Jobs
// ---------------------------------------------------------------------------

export async function fetchJobs(
  status?: string,
  limit = 50,
): Promise<{ jobs: Job[] }> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (status) params.set("status", status);
  return apiFetch<{ jobs: Job[] }>(`/jobs?${params}`);
}

export async function fetchJob(jobId: string): Promise<JobDetail> {
  return apiFetch<JobDetail>(`/jobs/${jobId}`);
}

export async function submitTheorem(body: {
  statement: string;
  lean_stub?: string;
  hints?: string;
  tier?: number;
  parallel_agents?: number;
  max_turns?: number;
}): Promise<{ job_id: string; status: string }> {
  return apiFetch("/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function submitLeanFile(body: {
  lean_source: string;
  description?: string;
  tier?: number;
  parallel_agents?: number;
  max_turns?: number;
}): Promise<{ job_id: string; status: string }> {
  return apiFetch("/jobs/lean-file", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function cancelJob(jobId: string): Promise<{ status: string }> {
  return apiFetch(`/jobs/${jobId}/cancel`, { method: "POST" });
}

export function subscribeJobStream(
  jobId: string,
  onAttempt: (a: Attempt) => void,
  onDone: (status: string) => void,
): EventSource {
  const es = new EventSource(`${BASE}/jobs/${jobId}/stream`);
  es.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.type === "attempt") {
      onAttempt(data as unknown as Attempt);
    } else if (data.type === "done") {
      onDone(data.status);
      es.close();
    }
  };
  es.onerror = () => {
    es.close();
    onDone("disconnected");
  };
  return es;
}

// ---------------------------------------------------------------------------
// Problems
// ---------------------------------------------------------------------------

export async function fetchProblems(
  source?: string,
  limit = 50,
): Promise<{ problems: Problem[] }> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (source) params.set("source", source);
  return apiFetch<{ problems: Problem[] }>(`/problems?${params}`);
}

export async function fetchProblem(id: string): Promise<Problem> {
  return apiFetch<Problem>(`/problems/${id}`);
}

export async function createProblem(body: {
  title: string;
  statement: string;
  lean_source?: string;
  source?: string;
  difficulty?: string;
  tags?: string;
  notes?: string;
}): Promise<{ id: string }> {
  return apiFetch("/problems", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function updateProblem(
  id: string,
  body: Partial<Problem>,
): Promise<void> {
  await apiFetch(`/problems/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function deleteProblem(id: string): Promise<void> {
  await apiFetch(`/problems/${id}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Capabilities / diagnostics / logs
// ---------------------------------------------------------------------------

export interface McpToolInfo {
  name: string;
  description: string;
}

export async function fetchCapabilities(): Promise<{
  server: string;
  version: string;
  transport: string;
  tools: McpToolInfo[];
}> {
  return apiFetch("/capabilities");
}

export async function fetchDiagnostics(): Promise<{
  server: string;
  version: string;
  checked_at: string;
  tools: string[];
  lean_workspace: { ok: boolean | null; message: string };
  jobs: Record<string, number>;
  live_tasks: number;
  recent_errors: string[];
}> {
  return apiFetch("/v1/diagnostics");
}

export async function fetchLogs(
  limit = 200,
  level?: string,
): Promise<{
  path: string;
  exists: boolean;
  count: number;
  entries: string[];
}> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (level) params.set("level", level);
  return apiFetch(`/logs?${params}`);
}

// ---------------------------------------------------------------------------
// LLM registry + chat proxy (the ONLY path the Chat page may use)
// ---------------------------------------------------------------------------

export interface LlmProvider {
  id: string;
  label: string;
  tier: number;
  model: string;
  base_url?: string;
  free: boolean;
  detected?: boolean;
  configured?: boolean;
}

export async function fetchLlmProviders(): Promise<{
  providers: LlmProvider[];
}> {
  return apiFetch("/llm/providers");
}

export async function fetchLlmDiscover(): Promise<{
  ollama: boolean;
  lm_studio: boolean;
}> {
  return apiFetch("/llm/discover");
}

export async function fetchLlmModels(): Promise<{
  models: string[];
  live: boolean;
}> {
  return apiFetch("/llm/models");
}

export async function fetchLlmOnboarding(): Promise<{
  facts: string[];
  recommended_path: string;
  ollama_detected: boolean;
}> {
  return apiFetch("/llm/onboarding");
}

export interface ChatMsg {
  role: string;
  content: string;
}

export async function postLlmChat(body: {
  messages: ChatMsg[];
  system?: string;
  tier?: number;
}): Promise<{ reply: string; tier: number; model: string }> {
  return apiFetch("/llm/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function streamLlmChat(
  body: { messages: ChatMsg[]; system?: string; tier?: number },
  onToken: (token: string) => void,
): Promise<void> {
  const res = await fetch(`${BASE}/llm/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body)
    throw new Error(`Chat stream returned ${res.status}`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop() ?? "";
    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data:")) continue;
      const payload = line.slice(5).trim();
      if (payload === "[DONE]") return;
      try {
        const data = JSON.parse(payload);
        if (data.error) throw new Error(data.error);
        const token = data.choices?.[0]?.delta?.content;
        if (token) onToken(token);
      } catch (e) {
        if (e instanceof Error && e.message !== payload) throw e;
      }
    }
  }
}
