import type { HealthResponse, Meeting, Member, Project } from "./types";

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
};
