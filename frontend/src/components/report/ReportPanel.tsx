"use client";

import { X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";

import { Button } from "@/components/ui/button";
import type { ReportData } from "@/lib/types";

type Props = {
  report: ReportData;
  onClose: () => void;
};

export function ReportPanel({ report, onClose }: Props) {
  const formattedDate = report.updatedAt.toLocaleString("ja-JP", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div className="flex h-full flex-col">
      <div className="flex shrink-0 items-center justify-between border-b px-6 py-3">
        <h2 className="text-sm font-semibold">📋 アサイン提案レポート</h2>
        <div className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground">{formattedDate}</span>
          <Button
            size="icon"
            variant="ghost"
            className="h-6 w-6"
            onClick={onClose}
            aria-label="レポートを閉じる"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto px-6 py-4">
        <div className="markdown-body max-w-none">
          <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
            {report.markdown}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
