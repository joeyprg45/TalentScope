"use client";

import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { useChatContext } from "@/context/ChatContext";
import type { ChatStatus } from "@/lib/types";
import { MessageInput } from "./MessageInput";
import { MessageList } from "./MessageList";

export function ChatPanel() {
  const { isOpen, closeChat, messages, status, sendMessage, toolCallLog } = useChatContext();

  return (
    <Sheet
      open={isOpen}
      onOpenChange={(open: boolean) => {
        if (!open) closeChat();
      }}
    >
      <SheetContent
        side="right"
        className="data-[side=right]:w-[420px] data-[side=right]:sm:max-w-[420px] flex flex-col gap-0 p-0"
      >
        <SheetHeader className="border-b px-4 py-3">
          <SheetTitle className="flex items-center gap-2 text-sm">
            AI チャット
            <StatusDot status={status} />
          </SheetTitle>
        </SheetHeader>
        <MessageList messages={messages} status={status} toolCallLog={toolCallLog} />
        <MessageInput
          onSend={sendMessage}
          disabled={status === "streaming" || status === "connecting"}
        />
      </SheetContent>
    </Sheet>
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
