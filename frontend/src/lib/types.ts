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
export type ToolCallKind = "tool" | "subagent";

export type ToolCallItem = {
  id: string;
  toolName: string;
  displayName: string;
  status: ToolCallStatus;
  args?: Record<string, string>;
  kind?: ToolCallKind; // 省略時は "tool"
  children?: ToolCallItem[]; // サブエージェント内部のツール呼び出し
};

export type ClarificationOption = {
  id: string;
  label: string;
  description?: string;
};

export type ClarificationPrompt = {
  id: string;
  question: string;
  options: ClarificationOption[];
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

export type ChatEntry = { role: "user" | "assistant"; content: string };

export type ChatSessionItem = {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
};

export type TraceEntry = Record<string, unknown>;

export type SavedReport = {
  id: string;
  type: "assignment" | "skill";
  title: string;
  markdown: string;
  createdAt: string;       // ISO 8601
  axis?: string | null;
  member_id?: string | null;
  project_id?: string | null;
  chat_history?: ChatEntry[];
};
