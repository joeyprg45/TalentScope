import type { SavedReport } from "@/lib/types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function toSavedReport(raw: Record<string, unknown>): SavedReport {
  return {
    ...(raw as SavedReport),
    createdAt: raw.created_at as string,
    // chat_history, member_id, project_id, axis are passed through as-is
  };
}

export async function fetchReports(): Promise<SavedReport[]> {
  const res = await fetch(`${BASE}/api/reports`);
  if (!res.ok) throw new Error("Failed to fetch reports");
  const items = await res.json() as Record<string, unknown>[];
  return items.map(toSavedReport);
}

export async function fetchReport(id: string): Promise<SavedReport> {
  const res = await fetch(`${BASE}/api/reports/${id}`);
  if (!res.ok) throw new Error("Report not found");
  return toSavedReport(await res.json() as Record<string, unknown>);
}

export async function deleteReport(id: string): Promise<void> {
  const res = await fetch(`${BASE}/api/reports/${id}`, { method: "DELETE" });
  if (!res.ok && res.status !== 404) throw new Error("Failed to delete report");
}

export async function tagReport(
  id: string,
  data: { member_id?: string | null; project_id?: string | null },
): Promise<SavedReport> {
  const res = await fetch(`${BASE}/api/reports/${id}/tag`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to tag report");
  return toSavedReport(await res.json() as Record<string, unknown>);
}
