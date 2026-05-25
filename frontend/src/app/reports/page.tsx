"use client";

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import { Download, FileText } from "lucide-react";
import { loadReports } from "@/lib/reportStorage";
import type { SavedReport } from "@/lib/types";

const TYPE_LABEL: Record<SavedReport["type"], string> = {
  assignment: "アサイン提案",
  skill: "スキル分析",
};

const TYPE_COLOR: Record<SavedReport["type"], string> = {
  assignment: "bg-primary/10 text-primary",
  skill: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
};

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("ja-JP", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function ReportsPage() {
  const [reports, setReports] = useState<SavedReport[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    const saved = loadReports();
    setReports(saved);
    if (saved.length > 0) setSelectedId(saved[0].id);
  }, []);

  const selected = reports.find((r) => r.id === selectedId) ?? null;

  const download = () => {
    if (!selected) return;
    const blob = new Blob([selected.markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${selected.type}-report-${selected.createdAt.slice(0, 10)}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (reports.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-center text-muted-foreground">
        <FileText className="h-12 w-12 opacity-30" />
        <p className="text-base font-medium text-foreground">まだレポートはありません</p>
        <p className="text-sm">チャットからアサイン提案またはスキル分析を依頼してください。</p>
      </div>
    );
  }

  return (
    <div className="flex h-full overflow-hidden">
      {/* 左: レポート一覧 */}
      <aside className="flex w-56 shrink-0 flex-col gap-1 overflow-y-auto border-r p-3">
        <p className="mb-1 px-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          過去のレポート
        </p>
        {reports.map((r) => (
          <button
            key={r.id}
            onClick={() => setSelectedId(r.id)}
            className={[
              "w-full rounded-lg px-3 py-2 text-left transition-colors",
              r.id === selectedId
                ? "bg-primary/10 ring-1 ring-inset ring-primary"
                : "hover:bg-muted",
            ].join(" ")}
          >
            <span
              className={`mb-1 inline-block rounded-full px-2 py-0.5 text-[10px] font-medium ${TYPE_COLOR[r.type]}`}
            >
              {TYPE_LABEL[r.type]}
            </span>
            <p className="truncate text-xs font-medium leading-snug">{r.title}</p>
            <p className="mt-0.5 text-[10px] text-muted-foreground">{formatDate(r.createdAt)}</p>
          </button>
        ))}
      </aside>

      {/* 右: レポート本文 */}
      {selected ? (
        <div className="flex flex-1 flex-col overflow-hidden">
          {/* ヘッダー */}
          <div className="flex shrink-0 items-center justify-between border-b px-6 py-3">
            <div className="flex items-center gap-2">
              <span
                className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${TYPE_COLOR[selected.type]}`}
              >
                {TYPE_LABEL[selected.type]}
              </span>
              <h2 className="text-sm font-semibold">{selected.title}</h2>
              <span className="text-xs text-muted-foreground">{formatDate(selected.createdAt)}</span>
            </div>
            <button
              onClick={download}
              className="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium transition-colors hover:bg-muted"
            >
              <Download className="h-3.5 w-3.5" />
              ダウンロード
            </button>
          </div>

          {/* コンテンツ */}
          <div className="flex-1 overflow-y-auto px-6 py-4">
            <div className="markdown-body max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
                {selected.markdown}
              </ReactMarkdown>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
