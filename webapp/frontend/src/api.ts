const BASE = "/api";
export const API_BASE = "http://127.0.0.1:10855";

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

export async function fetchJobs(status?: string, limit = 50): Promise<{ jobs: Job[] }> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (status) params.set("status", status);
  const res = await fetch(`${BASE}/jobs?${params}`);
  return res.json();
}

export async function fetchJob(jobId: string): Promise<JobDetail> {
  const res = await fetch(`${BASE}/jobs/${jobId}`);
  return res.json();
}

export async function submitTheorem(body: {
  statement: string;
  lean_stub?: string;
  hints?: string;
  tier?: number;
  parallel_agents?: number;
  max_turns?: number;
}): Promise<{ job_id: string; status: string }> {
  const res = await fetch(`${BASE}/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

export async function submitLeanFile(body: {
  lean_source: string;
  description?: string;
  tier?: number;
  parallel_agents?: number;
  max_turns?: number;
}): Promise<{ job_id: string; status: string }> {
  const res = await fetch(`${BASE}/jobs/lean-file`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

export async function cancelJob(jobId: string): Promise<{ status: string }> {
  const res = await fetch(`${BASE}/jobs/${jobId}/cancel`, { method: "POST" });
  return res.json();
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

export async function fetchProblems(
  source?: string,
  limit = 50,
): Promise<{ problems: Problem[] }> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (source) params.set("source", source);
  const res = await fetch(`${BASE}/problems?${params}`);
  return res.json();
}

export async function fetchProblem(id: string): Promise<Problem> {
  const res = await fetch(`${BASE}/problems/${id}`);
  return res.json();
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
  const res = await fetch(`${BASE}/problems`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

export async function updateProblem(
  id: string,
  body: Partial<Problem>,
): Promise<void> {
  await fetch(`${BASE}/problems/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function deleteProblem(id: string): Promise<void> {
  await fetch(`${BASE}/problems/${id}`, { method: "DELETE" });
}
