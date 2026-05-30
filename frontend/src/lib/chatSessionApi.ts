import type { ChatSessionItem, TraceEntry } from "@/lib/types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type RawSession = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  memory_extracted_at?: string | null;
};

export async function fetchChatSessions(): Promise<ChatSessionItem[]> {
  try {
    const res = await fetch(`${BASE}/api/chat/sessions`);
    if (!res.ok) return [];
    const data = (await res.json()) as RawSession[];
    return data.map((s) => ({
      id: s.id,
      title: s.title,
      createdAt: s.created_at,
      updatedAt: s.updated_at,
      memoryExtractedAt: s.memory_extracted_at ?? null,
    }));
  } catch {
    return [];
  }
}

export async function deleteChatSession(id: string): Promise<void> {
  await fetch(`${BASE}/api/chat/sessions/${id}`, { method: "DELETE" });
}

export async function fetchChatTrace(id: string): Promise<TraceEntry[]> {
  try {
    const res = await fetch(`${BASE}/api/chat/sessions/${id}/trace`);
    if (!res.ok) return [];
    return (await res.json()) as TraceEntry[];
  } catch {
    return [];
  }
}
