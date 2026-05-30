"use client";

import { Fragment, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";
import type { ChatMessage, ChatStatus, ToolCallItem } from "@/lib/types";
import { TypingIndicator } from "./TypingIndicator";
import { ToolCallLog } from "./ToolCallLog";

type Props = {
  messages: ChatMessage[];
  status: ChatStatus;
  toolCallLog?: ToolCallItem[];
};

export function MessageList({ messages, status, toolCallLog = [] }: Props) {
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages, status, toolCallLog]);

  const showTyping =
    status === "streaming" &&
    messages.at(-1)?.isStreaming &&
    messages.at(-1)?.content === "";

  return (
    <div ref={listRef} className="flex-1 overflow-y-auto px-4">
      <div className="flex flex-col gap-4 py-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center py-12 text-center text-sm text-muted-foreground">
            <p className="font-medium">TalentScope AI</p>
            <p className="mt-1">
              メンバー・プロジェクト・アサインメントについて
              <br />
              何でも聞いてください
            </p>
          </div>
        )}

        {messages.map((msg) => {
          // ストリーミング中・content なし → ToolCallLog をその位置に表示
          if (msg.isStreaming && !msg.content) {
            return (
              <Fragment key={msg.id}>
                {msg.detectedMode && (
                  <div className="flex items-start gap-2 pl-8 -mb-2">
                    <span className="inline-flex items-center rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary">
                      {msg.detectedMode.name}モード
                    </span>
                  </div>
                )}
                {toolCallLog.length > 0 && <ToolCallLog items={toolCallLog} />}
              </Fragment>
            );
          }

          // frozen tool-log-only（アサイン/スキルレポート用）
          if (!msg.content && !msg.isStreaming && msg.toolLog && msg.toolLog.length > 0) {
            return <ToolCallLog key={msg.id} items={msg.toolLog} frozen />;
          }

          return (
            <Fragment key={msg.id}>
              {msg.isStreaming && toolCallLog.length > 0 && <ToolCallLog items={toolCallLog} />}
              {!msg.isStreaming && msg.toolLog && msg.toolLog.length > 0 && (
                <ToolCallLog items={msg.toolLog} frozen />
              )}
              <MessageBubble message={msg} />
            </Fragment>
          );
        })}

        {showTyping && toolCallLog.length === 0 && <TypingIndicator />}
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex items-start gap-2", isUser && "flex-row-reverse")}>
      <Avatar className="mt-0.5 h-6 w-6 shrink-0">
        <AvatarFallback
          className={cn(
            "text-[10px]",
            isUser
              ? "bg-primary text-primary-foreground"
              : "bg-muted text-muted-foreground",
          )}
        >
          {isUser ? "U" : "AI"}
        </AvatarFallback>
      </Avatar>

      <div
        className={cn(
          "rounded-2xl px-3 py-2 text-sm",
          isUser
            ? "max-w-[75%] rounded-tr-sm bg-primary text-primary-foreground"
            : "max-w-[92%] rounded-tl-sm bg-muted text-foreground",
        )}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap break-words">{message.content}</p>
        ) : (
          <div className="markdown-body">
            {message.detectedMode && (
              <div className="mb-2">
                <span className="inline-flex items-center rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary">
                  {message.detectedMode.name}モード
                </span>
              </div>
            )}
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
            {message.isStreaming && message.content.length > 0 && (
              <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-current" />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
