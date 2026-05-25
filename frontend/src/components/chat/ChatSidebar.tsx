"use client";

import { useCallback, useRef, useState } from "react";

import { useChatContext } from "@/context/ChatContext";
import type { ChatStatus } from "@/lib/types";
import { AssignAxisSelector } from "./AssignAxisSelector";
import { MessageInput } from "./MessageInput";
import { MessageList } from "./MessageList";

const MIN_WIDTH = 260;
const MAX_WIDTH = 700;
const DEFAULT_WIDTH = 380;

export function ChatSidebar() {
  const {
    messages, status, sendMessage,
    pendingAssignmentContent, confirmAxisAndSend, cancelAssignmentPrompt,
    toolCallLog,
  } = useChatContext();

  const [width, setWidth] = useState(DEFAULT_WIDTH);
  const widthRef = useRef(DEFAULT_WIDTH);

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
      <div className="flex items-center border-b px-4 py-3">
        <span className="flex items-center gap-2 text-sm font-semibold">
          AI チャット
          <StatusDot status={status} />
        </span>
      </div>
      <MessageList messages={messages} status={status} toolCallLog={toolCallLog} />
      {pendingAssignmentContent !== null && (
        <AssignAxisSelector
          onChange={confirmAxisAndSend}
          onCancel={cancelAssignmentPrompt}
        />
      )}
      <MessageInput
        onSend={sendMessage}
        disabled={status === "streaming" || status === "connecting" || pendingAssignmentContent !== null}
      />
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
