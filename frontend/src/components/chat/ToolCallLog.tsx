"use client";

import { useEffect, useRef } from "react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import type { ToolCallItem } from "@/lib/types";

type Props = {
  items: ToolCallItem[];
  frozen?: boolean;
};

function ToolItem({ item, frozen, depth = 0 }: { item: ToolCallItem; frozen: boolean; depth?: number }) {
  const isSub = item.kind === "subagent";
  const isRunning = !frozen && item.status === "running";

  return (
    <>
      <li
        className={`flex items-center gap-2 text-[11px] ${
          isSub
            ? `ml-3 pl-2 border-l-2 border-indigo-300 dark:border-indigo-600 rounded-r pr-1.5 py-0.5 ${
                isRunning ? "bg-indigo-50/80 dark:bg-indigo-950/50" : ""
              }`
            : depth > 0
              ? "ml-6 pl-2 border-l border-indigo-200 dark:border-indigo-700 py-0.5"
              : ""
        }`}
      >
        {isRunning ? (
          <span
            className={`h-2.5 w-2.5 shrink-0 animate-spin rounded-full border-2 border-t-transparent ${
              isSub ? "border-indigo-500" : depth > 0 ? "border-indigo-400" : "border-muted-foreground"
            }`}
          />
        ) : (
          <span
            className={`h-2.5 w-2.5 shrink-0 leading-none ${
              isSub ? "text-indigo-500" : depth > 0 ? "text-indigo-400" : "text-emerald-500"
            }`}
          >
            ✓
          </span>
        )}
        <span
          className={`truncate ${
            isSub
              ? "font-medium text-indigo-700 dark:text-indigo-300"
              : depth > 0
                ? isRunning
                  ? "text-indigo-600 dark:text-indigo-400"
                  : "text-muted-foreground"
                : item.status === "done" || frozen
                  ? "text-muted-foreground"
                  : "text-foreground"
          }`}
        >
          {item.displayName}
        </span>
      </li>
      {item.children?.map((child) => (
        <ToolItem key={child.id} item={child} frozen={frozen} depth={depth + 1} />
      ))}
    </>
  );
}

export function ToolCallLog({ items, frozen = false }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!frozen && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [items, frozen]);

  if (items.length === 0) return null;

  return (
    <div className={`flex items-start gap-2 ${frozen ? "opacity-60" : ""}`}>
      <Avatar className="mt-0.5 h-6 w-6 shrink-0">
        <AvatarFallback className="text-[10px] bg-muted text-muted-foreground">
          AI
        </AvatarFallback>
      </Avatar>

      <div
        ref={scrollRef}
        className="max-h-48 w-full max-w-[75%] overflow-y-auto rounded-2xl rounded-tl-sm bg-muted px-3 py-2"
      >
        <ul className="flex flex-col gap-0.5">
          {items.map((item) => (
            <ToolItem key={item.id} item={item} frozen={frozen} />
          ))}
        </ul>
      </div>
    </div>
  );
}
