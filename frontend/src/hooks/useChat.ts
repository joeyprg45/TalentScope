import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type {
  ChatMessage,
  ChatStatus,
  ClarificationPrompt,
  ReportData,
  SavedReport,
  ToolCallItem,
} from "@/lib/types";
import type { AssignAxis } from "@/components/chat/AssignAxisSelector";
import { getToolLabel, getSubAgentLabel } from "@/lib/toolLabels";

const MAX_RECONNECT = 5;
const RECONNECT_BASE_MS = 1000;

function getOrCreateChatId(): string {
  const stored = localStorage.getItem("talentscope_chat_id");
  if (stored) return stored;
  const id = crypto.randomUUID();
  localStorage.setItem("talentscope_chat_id", id);
  return id;
}

export function useChat() {
  const router = useRouter();
  const sessionIdRef = useRef<string>(crypto.randomUUID());
  const chatIdRef = useRef<string>("");
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCountRef = useRef(0);
  const reportAccRef = useRef<string>("");
  const toolCallLogRef = useRef<ToolCallItem[]>([]);
  const currentReportIdRef = useRef<string | null>(null);
  const currentReportMarkdownRef = useRef<string>("");
  const selectedAxisRef = useRef<string>("ability");
  const currentSubagentIdRef = useRef<string | null>(null);

  const [activeChatId, setActiveChatId] = useState<string>("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [status, setStatus] = useState<ChatStatus>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [currentReport, setCurrentReport] = useState<ReportData | null>(null);
  const [currentSkillReport, setCurrentSkillReport] = useState<ReportData | null>(null);
  const [isReportLoading, setIsReportLoading] = useState(false);
  const [isSkillReportLoading, setIsSkillReportLoading] = useState(false);
  const [pendingAssignmentContent, setPendingAssignmentContent] = useState<string | null>(null);
  const [pendingClarification, setPendingClarification] = useState<ClarificationPrompt | null>(null);
  const [toolCallLog, setToolCallLog] = useState<ToolCallItem[]>([]);
  const [activeReportId, setActiveReportId] = useState<string | null>(null);
  const [activeReportTitle, setActiveReportTitle] = useState<string | null>(null);
  const [lastSavedReportId, setLastSavedReportId] = useState<string | null>(null);
  const [lastReportDiff, setLastReportDiff] = useState<{
    before: string;
    after: string;
    reportId: string;
  } | null>(null);

  // localStorage の旧データをクリア
  useEffect(() => {
    localStorage.removeItem("talentscope_reports");
  }, []);

  function connect() {
    const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const wsBase = base.replace(/^http/, "ws");
    const url = `${wsBase}/api/chat/ws?session_id=${sessionIdRef.current}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;
    setStatus("connecting");

    ws.onopen = () => {
      setStatus("connected");
      reconnectCountRef.current = 0;
      const chatId = chatIdRef.current || getOrCreateChatId();
      chatIdRef.current = chatId;
      setActiveChatId(chatId);
      ws.send(JSON.stringify({ type: "load_chat", chat_id: chatId }));
    };

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data as string) as Record<string, unknown>;

        if (data.type === "chat_loaded") {
          const msgs = (data.messages as Array<{ role: string; content: string }>) ?? [];
          setMessages(
            msgs
              .filter((m) => m.content.trim())
              .map((m) => ({
                id: crypto.randomUUID(),
                role: m.role as "user" | "assistant",
                content: m.content,
                isStreaming: false,
              })),
          );
        } else if (data.type === "tool_call") {
          const toolName = data.tool_name as string;
          const status = data.status as string;
          const args = data.args as Record<string, string> | undefined;
          if (toolName.startsWith("SubAgentPlugin-")) {
            // subagent_event で処理するためスキップ
          } else if (status === "start") {
            const item: ToolCallItem = {
              id: crypto.randomUUID(),
              toolName,
              displayName: getToolLabel(toolName, args),
              status: "running",
              args,
              kind: "tool",
            };
            if (currentSubagentIdRef.current) {
              toolCallLogRef.current = toolCallLogRef.current.map((t) =>
                t.id === currentSubagentIdRef.current
                  ? { ...t, children: [...(t.children ?? []), item] }
                  : t,
              );
            } else {
              toolCallLogRef.current = [...toolCallLogRef.current, item];
            }
            setToolCallLog([...toolCallLogRef.current]);
          } else {
            const updateDone = (items: ToolCallItem[]): ToolCallItem[] =>
              items.map((t) => {
                if (t.toolName === toolName && t.status === "running") return { ...t, status: "done" };
                if (t.children?.length) return { ...t, children: updateDone(t.children) };
                return t;
              });
            toolCallLogRef.current = updateDone(toolCallLogRef.current);
            setToolCallLog([...toolCallLogRef.current]);
          }
        } else if (data.type === "subagent_event") {
          const agentName = data.agent_name as string;
          const status = data.status as string;
          const args = data.args as Record<string, string> | undefined;
          if (status === "start") {
            const item: ToolCallItem = {
              id: crypto.randomUUID(),
              toolName: agentName,
              displayName: getSubAgentLabel(agentName, args),
              status: "running",
              args,
              kind: "subagent",
              children: [],
            };
            currentSubagentIdRef.current = item.id;
            toolCallLogRef.current = [...toolCallLogRef.current, item];
            setToolCallLog([...toolCallLogRef.current]);
          } else {
            currentSubagentIdRef.current = null;
            toolCallLogRef.current = toolCallLogRef.current.map((t) =>
              t.kind === "subagent" && t.toolName === agentName && t.status === "running"
                ? { ...t, status: "done" }
                : t,
            );
            setToolCallLog([...toolCallLogRef.current]);
          }
        } else if (data.type === "clarification_prompt") {
          setPendingClarification({
            id: data.id as string,
            question: data.question as string,
            options: (data.options as ClarificationPrompt["options"]) ?? [],
          });
        } else if (data.type === "chunk") {
          setMessages((prev) => {
            const last = prev.at(-1);
            if (last?.role === "assistant" && last.isStreaming)
              return [
                ...prev.slice(0, -1),
                { ...last, content: last.content + (data.text as string) },
              ];
            return prev;
          });
        } else if (data.type === "done") {
          const frozenLog = [...toolCallLogRef.current];
          toolCallLogRef.current = [];
          currentSubagentIdRef.current = null;
          setToolCallLog([]);
          setStatus("connected");
          const pr = data.pending_report as string | undefined;
          if (pr === "assignment") {
            setIsReportLoading(true);
            router.push("/reports");
          }
          if (pr === "skill") setIsSkillReportLoading(true);
          setMessages((prev) => {
            const last = prev.at(-1);
            if (!last?.isStreaming) return prev;
            if (!last.content.trim()) return prev.slice(0, -1);
            return [...prev.slice(0, -1), {
              ...last,
              isStreaming: false,
              toolLog: frozenLog.length > 0 ? frozenLog : undefined,
            }];
          });
        } else if (data.type === "axis_prompt") {
          setMessages((prev) => {
            const last = prev.at(-1);
            return last?.isStreaming ? prev.slice(0, -1) : prev;
          });
          setStatus("connected");
          setPendingAssignmentContent(data.original_content as string);
        } else if (data.type === "report_chunk") {
          reportAccRef.current += data.text as string;
        } else if (data.type === "report_done") {
          const reportType = (data.report_type as string) || "assignment";
          const reportId = data.report_id as string | undefined;
          const markdown = reportAccRef.current;
          const firstHeading = markdown.split("\n").find((l) => l.startsWith("#"));
          const title =
            firstHeading?.replace(/^#+\s*/, "").trim() ??
            (reportType.startsWith("skill") ? "スキル分析レポート" : "アサイン提案レポート");
          reportAccRef.current = "";
          const frozenLog = [...toolCallLogRef.current];
          toolCallLogRef.current = [];
          currentSubagentIdRef.current = null;
          setToolCallLog([]);
          setStatus("connected");

          if (reportId) {
            currentReportIdRef.current = reportId;
            setLastSavedReportId(reportId);
          }

          if (reportType === "assignment_refine") {
            const oldMarkdown = currentReportMarkdownRef.current;
            currentReportMarkdownRef.current = markdown;
            if (reportId && oldMarkdown) {
              setLastReportDiff({ before: oldMarkdown, after: markdown, reportId });
            }
            setCurrentReport({ markdown, updatedAt: new Date() });
            setIsReportLoading(false);
            setMessages((prev) => {
              const last = prev.at(-1);
              return last?.isStreaming ? prev.slice(0, -1) : prev;
            });
          } else {
            setMessages((prev) => {
              const last = prev.at(-1);
              const base = last?.isStreaming ? prev.slice(0, -1) : prev;
              if (frozenLog.length === 0) return base;
              return [
                ...base,
                {
                  id: crypto.randomUUID(),
                  role: "assistant" as const,
                  content: "",
                  isStreaming: false,
                  toolLog: frozenLog,
                },
              ];
            });
            router.push("/reports");
            if (reportType === "skill") {
              setCurrentSkillReport({ markdown, updatedAt: new Date() });
              setIsSkillReportLoading(false);
            } else {
              currentReportMarkdownRef.current = markdown;
              setCurrentReport({ markdown, updatedAt: new Date() });
              setIsReportLoading(false);
            }
          }
        } else if (data.type === "error") {
          toolCallLogRef.current = [];
          currentSubagentIdRef.current = null;
          setToolCallLog([]);
          setPendingClarification(null);
          setIsReportLoading(false);
          setIsSkillReportLoading(false);
          setErrorMessage(data.message as string);
          setStatus("error");
          setMessages((prev) => {
            const last = prev.at(-1);
            if (last?.isStreaming)
              return [
                ...prev.slice(0, -1),
                {
                  ...last,
                  content: `⚠️ ${data.message as string}`,
                  isStreaming: false,
                },
              ];
            return prev;
          });
        }
      } catch {
        // JSON parse 失敗は無視
      }
    };

    ws.onclose = (e) => {
      if (e.code === 1000) {
        setStatus("disconnected");
        return;
      }
      scheduleReconnect();
    };

    ws.onerror = () => {
      setStatus("error");
    };
  }

  function scheduleReconnect() {
    if (reconnectCountRef.current >= MAX_RECONNECT) {
      setStatus("disconnected");
      return;
    }
    setStatus("disconnected");
    const delay = RECONNECT_BASE_MS * 2 ** reconnectCountRef.current;
    reconnectCountRef.current += 1;
    setTimeout(connect, delay);
  }

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close(1000, "unmounted");
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const sendMessage = useCallback(
    (content: string) => {
      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN || status === "streaming") return;
      setMessages((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: "user", content },
        { id: crypto.randomUUID(), role: "assistant", content: "", isStreaming: true },
      ]);
      setStatus("streaming");
      ws.send(JSON.stringify({ type: "user_message", content }));
    },
    [status],
  );

  const confirmAxisAndSend = useCallback(
    (selectedAxis: AssignAxis) => {
      selectedAxisRef.current = selectedAxis;
      const content = pendingAssignmentContent;
      if (!content) return;
      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) return;
      setPendingAssignmentContent(null);
      setMessages((prev) => [
        ...prev.filter((m) => !m.isStreaming),
        { id: crypto.randomUUID(), role: "assistant", content: "", isStreaming: true },
      ]);
      setStatus("streaming");
      ws.send(JSON.stringify({ type: "axis_confirm", axis: selectedAxis, original_content: content }));
    },
    [pendingAssignmentContent],
  );

  const cancelAssignmentPrompt = useCallback(() => {
    setPendingAssignmentContent(null);
  }, []);

  const submitClarification = useCallback(
    (answerId: string, answerText?: string) => {
      const ws = wsRef.current;
      const cur = pendingClarification;
      if (!ws || ws.readyState !== WebSocket.OPEN || !cur) return;
      ws.send(
        JSON.stringify({
          type: "clarification_response",
          id: cur.id,
          answer_id: answerId,
          answer_text: answerText ?? "",
        }),
      );
      setPendingClarification(null);
    },
    [pendingClarification],
  );

  const clearMessages = useCallback(() => {
    setMessages([]);
    currentReportIdRef.current = null;
    currentReportMarkdownRef.current = "";
    setActiveReportId(null);
    setActiveReportTitle(null);
    setLastReportDiff(null);
  }, []);
  const clearReport = useCallback(() => setCurrentReport(null), []);
  const clearSkillReport = useCallback(() => setCurrentSkillReport(null), []);

  const setActiveReport = useCallback((report: SavedReport) => {
    setActiveReportId(report.id);
    setActiveReportTitle(report.title);
    currentReportIdRef.current = report.id;
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "set_active_report", report_id: report.id }));
    }
  }, []);

  const clearActiveReport = useCallback(() => {
    setActiveReportId(null);
    setActiveReportTitle(null);
    currentReportIdRef.current = null;
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "set_active_report", report_id: null }));
    }
  }, []);

  const newChat = useCallback(() => {
    const id = crypto.randomUUID();
    chatIdRef.current = id;
    setActiveChatId(id);
    localStorage.setItem("talentscope_chat_id", id);
    setMessages([]);
    currentReportIdRef.current = null;
    currentReportMarkdownRef.current = "";
    setActiveReportId(null);
    setActiveReportTitle(null);
    setLastReportDiff(null);
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "new_chat", chat_id: id }));
    }
  }, []);

  const loadChat = useCallback((chatId: string) => {
    chatIdRef.current = chatId;
    setActiveChatId(chatId);
    localStorage.setItem("talentscope_chat_id", chatId);
    setMessages([]);
    currentReportIdRef.current = null;
    currentReportMarkdownRef.current = "";
    setActiveReportId(null);
    setActiveReportTitle(null);
    setLastReportDiff(null);
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "load_chat", chat_id: chatId }));
    }
  }, []);

  return {
    activeChatId,
    messages, status, errorMessage, sendMessage, clearMessages,
    currentReport, clearReport, isReportLoading,
    currentSkillReport, clearSkillReport, isSkillReportLoading,
    pendingAssignmentContent, confirmAxisAndSend, cancelAssignmentPrompt,
    pendingClarification, submitClarification,
    toolCallLog,
    activeReportId, activeReportTitle, setActiveReport, clearActiveReport,
    lastSavedReportId, lastReportDiff,
    newChat, loadChat,
  };
}
