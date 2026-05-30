import type { AbsoluteConstraint, ExtractionResult, HealthResponse, Meeting, Member, Project, PromptNode } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new ApiError(res.status, text || res.statusText);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<HealthResponse>("/api/health"),
  members: () => request<Member[]>("/api/members"),
  member: (id: string) => request<Member>(`/api/members/${encodeURIComponent(id)}`),
  projects: () => request<Project[]>("/api/projects"),
  project: (id: string) =>
    request<Project>(`/api/projects/${encodeURIComponent(id)}`),
  meetings: () => request<Meeting[]>("/api/meetings"),
  prompts: () => request<PromptNode[]>("/api/prompts"),
  updatePrompt: (id: string, body: { ceo_layer?: string; trigger_conditions?: string }) =>
    request<PromptNode>(`/api/prompts/${encodeURIComponent(id)}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  createPrompt: (body: {
    id: string;
    parent_id?: string | null;
    name: string;
    description?: string;
    ceo_layer?: string;
    is_selectable?: boolean;
  }) => request<PromptNode>("/api/prompts", { method: "POST", body: JSON.stringify(body) }),
  deletePrompt: (id: string) =>
    fetch(`${BASE}/api/prompts/${encodeURIComponent(id)}`, { method: "DELETE" }),
  memory: {
    listConstraints: () => request<AbsoluteConstraint[]>("/api/memory/constraints"),
    createConstraint: (content: string, related_member_ids?: string[]) =>
      request<AbsoluteConstraint>("/api/memory/constraints", {
        method: "POST",
        body: JSON.stringify({ content, related_member_ids: related_member_ids ?? [] }),
      }),
    updateConstraintStatus: (id: string, status: string) =>
      request<{ id: string; status: string }>(
        `/api/memory/constraints/${encodeURIComponent(id)}`,
        { method: "PATCH", body: JSON.stringify({ status }) }
      ),
    deleteConstraint: (id: string) =>
      fetch(`${BASE}/api/memory/constraints/${encodeURIComponent(id)}`, { method: "DELETE" }),
    getQualitative: () => request<{ content: string }>("/api/memory/qualitative"),
    updateQualitative: (content: string) =>
      request<{ content: string }>("/api/memory/qualitative", {
        method: "PUT",
        body: JSON.stringify({ content }),
      }),
    extractMemory: () => request<ExtractionResult>("/api/memory/extract", { method: "POST" }),
    getUnprocessedCount: () => request<{ count: number }>("/api/memory/unprocessed_count"),
  },
};
