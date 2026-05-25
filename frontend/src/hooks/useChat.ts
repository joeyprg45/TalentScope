import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { ChatMessage, ChatStatus, ReportData, ToolCallItem } from "@/lib/types";
import type { AssignAxis } from "@/components/chat/AssignAxisSelector";
import { saveReport } from "@/lib/reportStorage";
import { getToolLabel } from "@/lib/toolLabels";

const MAX_RECONNECT = 5;
const RECONNECT_BASE_MS = 1000;

export function useChat() {
  const router = useRouter();
  const sessionIdRef = useRef<string>(crypto.randomUUID());
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCountRef = useRef(0);
  const reportAccRef = useRef<string>("");
  const toolCallLogRef = useRef<ToolCallItem[]>([]);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [status, setStatus] = useState<ChatStatus>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [currentReport, setCurrentReport] = useState<ReportData | null>(null);
  const [currentSkillReport, setCurrentSkillReport] = useState<ReportData | null>(null);
  const [isReportLoading, setIsReportLoading] = useState(false);
  const [isSkillReportLoading, setIsSkillReportLoading] = useState(false);
  const [pendingAssignmentContent, setPendingAssignmentContent] = useState<string | null>(null);
  const [toolCallLog, setToolCallLog] = useState<ToolCallItem[]>([]);

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
    };

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data as string) as Record<string, unknown>;

        if (data.type === "tool_call") {
          const toolName = data.tool_name as string;
          const status = data.status as string;
          const args = data.args as Record<string, string> | undefined;
          if (status === "start") {
            const item: ToolCallItem = {
              id: `${toolName}-${Date.now()}`,
              toolName,
              displayName: getToolLabel(toolName, args),
              status: "running",
              args,
            };
            toolCallLogRef.current = [...toolCallLogRef.current, item];
            setToolCallLog([...toolCallLogRef.current]);
          } else {
            toolCallLogRef.current = toolCallLogRef.current.map((t) =>
              t.toolName === toolName && t.status === "running"
                ? { ...t, status: "done" }
                : t,
            );
            setToolCallLog([...toolCallLogRef.current]);
          }
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
          // バックエンドがアサイン提案と判定 → ストリーミングプレースホルダーを削除して軸セレクタ表示
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
          const markdown = reportAccRef.current;
          const firstHeading = markdown.split("\n").find((l) => l.startsWith("#"));
          const title =
            firstHeading?.replace(/^#+\s*/, "").trim() ??
            (reportType === "skill" ? "スキル分析レポート" : "アサイン提案レポート");
          saveReport({ type: reportType as "assignment" | "skill", title, markdown });
          reportAccRef.current = "";
          const frozenLog = [...toolCallLogRef.current];
          toolCallLogRef.current = [];
          setToolCallLog([]);
          setStatus("connected");
          const completionText = reportType === "skill"
            ? "スキル分析レポートが完成しました。レポートタブで確認できます。"
            : "アサイン提案レポートが完成しました。レポートタブで確認できます。";
          setMessages((prev) => {
            const last = prev.at(-1);
            const base = last?.isStreaming ? prev.slice(0, -1) : prev;
            const result = [...base];
            if (frozenLog.length > 0) {
              result.push({
                id: crypto.randomUUID(),
                role: "assistant" as const,
                content: "",
                isStreaming: false,
                toolLog: frozenLog,
              });
            }
            result.push({
              id: crypto.randomUUID(),
              role: "assistant" as const,
              content: completionText,
              isStreaming: false,
            });
            return result;
          });
          router.push("/reports");
          if (reportType === "skill") {
            setCurrentSkillReport({ markdown, updatedAt: new Date() });
            setIsSkillReportLoading(false);
          } else {
            setCurrentReport({ markdown, updatedAt: new Date() });
            setIsReportLoading(false);
          }
        } else if (data.type === "error") {
          toolCallLogRef.current = [];
          setToolCallLog([]);
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

  const clearMessages = useCallback(() => setMessages([]), []);
  const clearReport = useCallback(() => setCurrentReport(null), []);
  const clearSkillReport = useCallback(() => setCurrentSkillReport(null), []);

  return {
    messages, status, errorMessage, sendMessage, clearMessages,
    currentReport, clearReport, isReportLoading,
    currentSkillReport, clearSkillReport, isSkillReportLoading,
    pendingAssignmentContent, confirmAxisAndSend, cancelAssignmentPrompt,
    toolCallLog,
  };
}
