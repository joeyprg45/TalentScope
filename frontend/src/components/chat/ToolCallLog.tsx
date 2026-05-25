"use client";

import { useEffect, useRef } from "react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import type { ToolCallItem } from "@/lib/types";

type Props = {
  items: ToolCallItem[];
  frozen?: boolean;
};

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
            <li
              key={item.id}
              className="flex items-center gap-2 text-[11px]"
            >
              {!frozen && item.status === "running" ? (
                <span className="h-2.5 w-2.5 shrink-0 animate-spin rounded-full border-2 border-muted-foreground border-t-transparent" />
              ) : (
                <span className="h-2.5 w-2.5 shrink-0 text-emerald-500 leading-none">✓</span>
              )}
              <span
                className={`truncate ${
                  item.status === "done" || frozen
                    ? "text-muted-foreground"
                    : "text-foreground"
                }`}
              >
                {item.displayName}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
