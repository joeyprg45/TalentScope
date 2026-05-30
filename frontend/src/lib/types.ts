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

// --- Prompts ---
export type PromptNode = {
  id: string;
  parent_id: string | null;
  name: string;
  description: string;
  trigger_conditions: string;
  ceo_layer: string;
  is_system: boolean;
  is_selectable: boolean;
  children: PromptNode[];
};

// --- Chat ---
export type ChatRole = "user" | "assistant";

export type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  isStreaming?: boolean;
  toolLog?: ToolCallItem[];
  detectedMode?: { id: string; name: string };
};

export type ToolCallStatus = "running" | "done";
export type ToolCallKind = "tool" | "subagent" | "plan";

export type ToolCallItem = {
  id: string;
  toolName: string;
  displayName: string;
  status: ToolCallStatus;
  args?: Record<string, string>;
  kind?: ToolCallKind;
  planText?: string;
  children?: ToolCallItem[];
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
  memoryExtractedAt?: string | null;
};

// --- Memory ---
export type AbsoluteConstraint = {
  id: string;
  content: string;
  status: "pending" | "active" | "dismissed";
  source: "ai" | "manual";
  related_member_ids: string[];
  created_at: string;
  chat_id?: string | null;
};

export type ExtractionResult = {
  processed: number;
  constraints_found: number;
  qualitative_updated: boolean;
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
