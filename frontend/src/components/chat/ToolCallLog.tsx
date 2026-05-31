"use client";

import React, { useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import type { ToolCallItem } from "@/lib/types";

type Props = {
  items: ToolCallItem[];
  frozen?: boolean;
};

const planMdComponents = {
  h1: ({ children }: { children?: React.ReactNode }) => <span className="block font-semibold">{children}</span>,
  h2: ({ children }: { children?: React.ReactNode }) => <span className="block font-semibold">{children}</span>,
  h3: ({ children }: { children?: React.ReactNode }) => <span className="block font-medium">{children}</span>,
  p:  ({ children }: { children?: React.ReactNode }) => <span className="block">{children}</span>,
  ul: ({ children }: { children?: React.ReactNode }) => <ul className="list-disc pl-3">{children}</ul>,
  ol: ({ children }: { children?: React.ReactNode }) => <ol className="list-decimal pl-3">{children}</ol>,
  li: ({ children }: { children?: React.ReactNode }) => <li>{children}</li>,
};

function PlanItem({ item }: { item: ToolCallItem }) {
  return (
    <li className="mb-1.5 pb-1.5 border-b border-border/30">
      <p className="mb-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
        分析プラン
      </p>
      <div className="text-[11px] text-foreground/80 leading-relaxed">
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={planMdComponents}>{item.planText ?? ""}</ReactMarkdown>
      </div>
    </li>
  );
}

function EvalItem({ item, frozen }: { item: ToolCallItem; frozen: boolean }) {
  const passed = item.evalPassed;
  return (
    <li className={`my-1 rounded-lg px-3 py-2 text-[11px] border ${
      passed
        ? "border-emerald-300 bg-emerald-50/60 dark:bg-emerald-950/30"
        : "border-amber-300 bg-amber-50/60 dark:bg-amber-950/30"
    }`}>
      <div className="flex items-center gap-1.5 font-medium">
        <span className={passed ? "text-emerald-600 dark:text-emerald-400" : "text-amber-600 dark:text-amber-400"}>
          {passed ? "✓" : "✗"}
        </span>
        <span>{item.displayName}</span>
      </div>
      <div className="mt-1 text-muted-foreground">
        絶対条件: {item.evalPassedConstraints}/{item.evalTotalConstraints} 通過
        {item.evalViolations && item.evalViolations.length > 0 && (
          <ul className="mt-0.5 list-disc pl-4 text-red-600 dark:text-red-400">
            {item.evalViolations.map((v, i) => <li key={i}>{v}</li>)}
          </ul>
        )}
      </div>
      <div className="mt-0.5 text-muted-foreground">
        定性方針: {item.evalQualitativeOk ? "✓ 通過" : "✗ 未通過"}
        {item.evalAdvice && (
          <p className="mt-0.5 text-amber-700 dark:text-amber-400">{item.evalAdvice}</p>
        )}
      </div>
    </li>
  );
}

function EvalCorrectionItem({ item, frozen }: { item: ToolCallItem; frozen: boolean }) {
  const isRunning = !frozen && item.status === "running";
  return (
    <li className="flex items-center gap-2 text-[11px] my-0.5 text-indigo-600 dark:text-indigo-400 font-medium">
      {isRunning ? (
        <span className="h-2.5 w-2.5 shrink-0 animate-spin rounded-full border-2 border-t-transparent border-indigo-500" />
      ) : (
        <span className="h-2.5 w-2.5 shrink-0 text-indigo-500">↻</span>
      )}
      <span>{item.displayName}</span>
    </li>
  );
}

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
        className="max-h-72 w-full max-w-[75%] overflow-y-auto rounded-2xl rounded-tl-sm bg-muted px-3 py-2"
      >
        <ul className="flex flex-col gap-0.5">
          {items.map((item) =>
            item.kind === "plan"
              ? <PlanItem key={item.id} item={item} />
              : item.kind === "eval"
                ? <EvalItem key={item.id} item={item} frozen={frozen} />
                : item.kind === "eval_correction"
                  ? <EvalCorrectionItem key={item.id} item={item} frozen={frozen} />
                  : <ToolItem key={item.id} item={item} frozen={frozen} />
          )}
        </ul>
      </div>
    </div>
  );
}
