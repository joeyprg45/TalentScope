"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { MessageSquarePlus, History, Trash2, Terminal, Download, RefreshCw } from "lucide-react";

import { useChatContext } from "@/context/ChatContext";
import { fetchChatSessions, deleteChatSession, fetchChatTrace } from "@/lib/chatSessionApi";
import type { ChatSessionItem, ChatStatus, TraceEntry } from "@/lib/types";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { AssignAxisSelector } from "./AssignAxisSelector";
import { ClarificationPanel } from "./ClarificationPanel";
import { MessageInput } from "./MessageInput";
import { MessageList } from "./MessageList";

const MIN_WIDTH = 260;
const MAX_WIDTH = 700;
const DEFAULT_WIDTH = 380;

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("ja-JP", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function ChatSidebar() {
  const {
    activeChatId,
    messages, status, sendMessage,
    pendingAssignmentContent, confirmAxisAndSend, cancelAssignmentPrompt,
    pendingClarification, submitClarification,
    toolCallLog,
    activeReportTitle, clearActiveReport,
    newChat, loadChat,
  } = useChatContext();

  const [width, setWidth] = useState(DEFAULT_WIDTH);
  const widthRef = useRef(DEFAULT_WIDTH);
  const [showSessions, setShowSessions] = useState(false);
  const [sessions, setSessions] = useState<ChatSessionItem[]>([]);
  const [showTrace, setShowTrace] = useState(false);
  const [traceData, setTraceData] = useState<TraceEntry[]>([]);
  const [traceLoading, setTraceLoading] = useState(false);

  useEffect(() => {
    if (!showSessions) return;
    fetchChatSessions().then(setSessions);
  }, [showSessions]);

  const handleNewChat = useCallback(() => {
    newChat();
    setShowSessions(false);
  }, [newChat]);

  const handleLoadChat = useCallback((id: string) => {
    loadChat(id);
    setShowSessions(false);
  }, [loadChat]);

  const handleDeleteSession = useCallback(async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    await deleteChatSession(id);
    setSessions((prev) => prev.filter((s) => s.id !== id));
  }, []);

  const handleOpenTrace = useCallback(async () => {
    if (!activeChatId) return;
    setShowTrace(true);
    setTraceLoading(true);
    const data = await fetchChatTrace(activeChatId);
    setTraceData(data);
    setTraceLoading(false);
  }, [activeChatId]);

  const handleRefreshTrace = useCallback(async () => {
    if (!activeChatId) return;
    setTraceLoading(true);
    const data = await fetchChatTrace(activeChatId);
    setTraceData(data);
    setTraceLoading(false);
  }, [activeChatId]);

  const handleDownloadTrace = useCallback(() => {
    const json = JSON.stringify(traceData, null, 2);
    const blob = new Blob([json], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `trace-${activeChatId || "unknown"}-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [traceData, activeChatId]);

  const onResizeMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const startWidth = widthRef.current;

    const onMouseMove = (e: MouseEvent) => {
      const newWidth = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, startWidth + (startX - e.clientX)));
      widthRef.current = newWidth;
      setWidth(newWidth);
    };

    const onMouseUp = () => {
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
    };

    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
  }, []);

  return (
    <aside className="relative flex shrink-0 flex-col border-l bg-card" style={{ width }}>
      <div
        className="absolute inset-y-0 left-[-3px] z-10 w-1.5 cursor-col-resize transition-colors hover:bg-primary/30 active:bg-primary/50"
        onMouseDown={onResizeMouseDown}
      />

      {/* ヘッダー: タイトル + 操作ボタン */}
      <div className="flex items-center justify-between border-b px-4 py-2.5">
        <span className="flex items-center gap-2 text-sm font-semibold">
          AI チャット
          <StatusDot status={status} />
        </span>
        <div className="flex items-center gap-1">
          <button
            onClick={handleOpenTrace}
            className="rounded p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            aria-label="AIトレースログ"
            title="AIトレースログ"
            disabled={!activeChatId}
          >
            <Terminal className="h-4 w-4" />
          </button>
          <button
            onClick={() => setShowSessions((v) => !v)}
            className={[
              "rounded p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
              showSessions ? "bg-muted text-foreground" : "",
            ].join(" ")}
            aria-label="チャット履歴"
            title="チャット履歴"
          >
            <History className="h-4 w-4" />
          </button>
          <button
            onClick={handleNewChat}
            className="rounded p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            aria-label="新規チャット"
            title="新規チャット"
          >
            <MessageSquarePlus className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* セッション一覧 */}
      {showSessions && (
        <div className="max-h-52 overflow-y-auto border-b bg-muted/20">
          {sessions.length === 0 ? (
            <p className="px-4 py-3 text-xs text-muted-foreground">チャット履歴はありません</p>
          ) : (
            sessions.map((s) => (
              <div
                key={s.id}
                className="group flex cursor-pointer items-start justify-between gap-2 px-4 py-2 hover:bg-muted"
                onClick={() => handleLoadChat(s.id)}
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-medium">{s.title}</p>
                  <p className="text-[10px] text-muted-foreground">{formatDate(s.updatedAt)}</p>
                </div>
                <button
                  onClick={(e) => handleDeleteSession(e, s.id)}
                  className="mt-0.5 shrink-0 rounded p-0.5 text-muted-foreground opacity-0 transition-opacity hover:text-destructive group-hover:opacity-100"
                  aria-label="削除"
                >
                  <Trash2 className="h-3 w-3" />
                </button>
              </div>
            ))
          )}
        </div>
      )}

      {/* 編集対象レポート */}
      {activeReportTitle && (
        <div className="flex items-center gap-1.5 border-b bg-primary/5 px-4 py-2 text-xs">
          <span className="text-muted-foreground">編集対象:</span>
          <span className="flex-1 truncate font-medium">{activeReportTitle}</span>
          <button
            onClick={clearActiveReport}
            className="text-muted-foreground hover:text-foreground"
            aria-label="編集対象を解除"
          >
            ✕
          </button>
        </div>
      )}

      <MessageList messages={messages} status={status} toolCallLog={toolCallLog} />
      {pendingAssignmentContent !== null && (
        <AssignAxisSelector
          onChange={confirmAxisAndSend}
          onCancel={cancelAssignmentPrompt}
        />
      )}
      {pendingClarification !== null && (
        <ClarificationPanel
          prompt={pendingClarification}
          onSubmit={submitClarification}
        />
      )}
      <MessageInput
        onSend={sendMessage}
        disabled={
          status === "streaming" ||
          status === "connecting" ||
          pendingAssignmentContent !== null ||
          pendingClarification !== null
        }
      />

      <Dialog open={showTrace} onOpenChange={setShowTrace}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <div className="flex items-center justify-between pr-6">
              <DialogTitle className="flex items-center gap-2 text-sm font-semibold">
                <Terminal className="h-4 w-4" />
                AIトレースログ
              </DialogTitle>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleRefreshTrace}
                  className="flex items-center gap-1 rounded px-2 py-1 text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
                  disabled={traceLoading}
                >
                  <RefreshCw className={`h-3 w-3 ${traceLoading ? "animate-spin" : ""}`} />
                  更新
                </button>
                <button
                  onClick={handleDownloadTrace}
                  className="flex items-center gap-1 rounded px-2 py-1 text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
                  disabled={traceData.length === 0}
                >
                  <Download className="h-3 w-3" />
                  ダウンロード
                </button>
              </div>
            </div>
          </DialogHeader>
          <div className="overflow-auto max-h-[60vh] rounded border bg-muted/30 p-3">
            {traceLoading ? (
              <p className="text-xs text-muted-foreground">読み込み中...</p>
            ) : traceData.length === 0 ? (
              <p className="text-xs text-muted-foreground">ログがありません（まだメッセージを送信していないか、このチャットのセッションが保存されていません）</p>
            ) : (
              <pre className="text-[11px] leading-relaxed whitespace-pre-wrap break-words font-mono">
                {JSON.stringify(traceData, null, 2)}
              </pre>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </aside>
  );
}

function StatusDot({ status }: { status: ChatStatus }) {
  const color =
    status === "connected" || status === "streaming"
      ? "bg-green-500"
      : status === "connecting"
        ? "bg-yellow-500 animate-pulse"
        : "bg-red-500";
  return <span className={`h-2 w-2 rounded-full ${color}`} />;
}
