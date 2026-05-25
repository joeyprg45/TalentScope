export type Member = {
  member_id: string;
  name: string;
  role?: string | null;
  skills?: string[];
  years_experience?: number | null;
  monthly_cost?: number | null;
};

export type Assignment = {
  member_id: string;
  role?: string | null;
  start?: string | null;
  end?: string | null;
};

export type Project = {
  project_id: string;
  name: string;
  status?: string | null;
  period?: { start: string; end: string } | null;
  assignments?: Assignment[];
  required_skills?: string[];
};

export type Meeting = {
  meeting_id?: string;
  title?: string;
  date?: string;
  meeting_type?: string;
  project_id?: string;
  participants?: string[];
  overall_summary?: string;
};

export type HealthResponse = { status: string };

// --- Chat ---
export type ChatRole = "user" | "assistant";

export type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  isStreaming?: boolean;
  toolLog?: ToolCallItem[];
};

export type ToolCallStatus = "running" | "done";

export type ToolCallItem = {
  id: string;
  toolName: string;
  displayName: string;
  status: ToolCallStatus;
  args?: Record<string, string>;
};

export type ChatStatus =
  | "idle"
  | "connecting"
  | "connected"
  | "streaming"
  | "error"
  | "disconnected";

// --- Report ---
export type ReportData = {
  markdown: string;
  updatedAt: Date;
};

export type SavedReport = {
  id: string;
  type: "assignment" | "skill";
  title: string;
  markdown: string;
  createdAt: string; // ISO 8601
};
