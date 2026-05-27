"use client";

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import { diffArrays } from "diff";
import { ChevronDown, ChevronRight, Download, FileText, Trash2 } from "lucide-react";
import { fetchReports, deleteReport, tagReport } from "@/lib/reportApi";
import type { SavedReport, ChatEntry } from "@/lib/types";
import { useChatContext } from "@/context/ChatContext";
import type { Member, Project } from "@/lib/types";

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

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function fetchMembers(): Promise<Member[]> {
  try {
    const res = await fetch(`${BASE}/api/members`);
    if (!res.ok) return [];
    return res.json() as Promise<Member[]>;
  } catch {
    return [];
  }
}

async function fetchProjects(): Promise<Project[]> {
  try {
    const res = await fetch(`${BASE}/api/projects`);
    if (!res.ok) return [];
    return res.json() as Promise<Project[]>;
  } catch {
    return [];
  }
}

function RenderedDiffView({ before, after }: { before: string; after: string }) {
  const beforeBlocks = before.split(/\n\n+/);
  const afterBlocks = after.split(/\n\n+/);
  const changes = diffArrays(beforeBlocks, afterBlocks);

  return (
    <div className="space-y-2">
      {changes.flatMap((change, i) =>
        change.value.map((block, j) => {
          if (!block.trim()) return null;
          const cls = change.added
            ? "border-l-4 border-green-500 bg-green-50 dark:bg-green-950/20 pl-4"
            : change.removed
            ? "border-l-4 border-red-400 bg-red-50 dark:bg-red-950/20 pl-4 opacity-60"
            : "";
          return (
            <div key={`${i}-${j}`} className={cls}>
              <div className="markdown-body max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
                  {block}
                </ReactMarkdown>
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}

function ChatHistorySection({ history }: { history: ChatEntry[] }) {
  const [open, setOpen] = useState(false);
  if (history.length === 0) return null;
  return (
    <div className="mt-6 border-t pt-4">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 text-sm font-semibold text-muted-foreground hover:text-foreground"
      >
        {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        編集履歴 ({history.length}件)
      </button>
      {open && (
        <div className="mt-3 space-y-2">
          {history.map((entry, i) => (
            <div
              key={i}
              className={[
                "rounded-md px-3 py-2 text-xs",
                entry.role === "user"
                  ? "bg-muted text-foreground"
                  : "bg-primary/5 text-foreground",
              ].join(" ")}
            >
              <span className="mr-1.5 font-medium text-muted-foreground">
                {entry.role === "user" ? "👤" : "🤖"}
              </span>
              {entry.content}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ReportsPage() {
  const [reports, setReports] = useState<SavedReport[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [filterType, setFilterType] = useState<"all" | "assignment" | "skill">("all");
  const [filterMember, setFilterMember] = useState<string>("all");
  const [filterProject, setFilterProject] = useState<string>("all");
  const [showDiff, setShowDiff] = useState(false);
  const { setActiveReport, activeReportId, clearActiveReport, lastSavedReportId, lastReportDiff } = useChatContext();

  useEffect(() => {
    fetchReports().then(setReports).catch(() => setReports([]));
    fetchMembers().then(setMembers);
    fetchProjects().then(setProjects);
  }, []);

  useEffect(() => {
    if (!lastSavedReportId) return;
    fetchReports().then((data) => {
      setReports(data);
      if (data.find((r) => r.id === lastSavedReportId)) {
        setSelectedId(lastSavedReportId);
      }
    }).catch(() => {});
  }, [lastSavedReportId]);

  useEffect(() => {
    if (!lastReportDiff) return;
    setReports((prev) =>
      prev.map((r) =>
        r.id === lastReportDiff.reportId
          ? { ...r, markdown: lastReportDiff.after }
          : r,
      ),
    );
  }, [lastReportDiff]);

  const filtered = reports.filter((r) => {
    if (filterType !== "all" && r.type !== filterType) return false;
    if (filterMember !== "all" && r.member_id !== filterMember) return false;
    if (filterProject !== "all" && r.project_id !== filterProject) return false;
    return true;
  });

  useEffect(() => {
    if (filtered.length > 0 && (!selectedId || !filtered.find((r) => r.id === selectedId))) {
      setSelectedId(filtered[0].id);
    }
  }, [filtered, selectedId]);

  useEffect(() => { setShowDiff(false); }, [selectedId]);

  const selected = reports.find((r) => r.id === selectedId) ?? null;
  const diffAvailable = lastReportDiff != null && lastReportDiff.reportId === selectedId;

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

  const handleDelete = async (id: string) => {
    await deleteReport(id);
    setReports((prev) => prev.filter((r) => r.id !== id));
    if (selectedId === id) setSelectedId(null);
  };

  const handleTag = async (
    id: string,
    field: "member_id" | "project_id",
    value: string | null,
  ) => {
    const report = reports.find((r) => r.id === id);
    if (!report) return;
    const updated = await tagReport(id, {
      member_id: field === "member_id" ? value : report.member_id ?? null,
      project_id: field === "project_id" ? value : report.project_id ?? null,
    });
    setReports((prev) => prev.map((r) => (r.id === id ? updated : r)));
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
      {/* 左: レポート一覧 + フィルター */}
      <aside className="flex w-64 shrink-0 flex-col gap-1 overflow-y-auto border-r p-3">
        {/* フィルター */}
        <div className="mb-2 space-y-1.5 rounded-lg border bg-muted/30 p-2.5">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">フィルター</p>
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value as typeof filterType)}
            className="w-full rounded border bg-background px-2 py-1 text-xs"
          >
            <option value="all">全種別</option>
            <option value="assignment">アサイン提案</option>
            <option value="skill">スキル分析</option>
          </select>
          {members.length > 0 && (
            <select
              value={filterMember}
              onChange={(e) => setFilterMember(e.target.value)}
              className="w-full rounded border bg-background px-2 py-1 text-xs"
            >
              <option value="all">全メンバー</option>
              {members.map((m) => (
                <option key={m.member_id} value={m.member_id}>{m.name}</option>
              ))}
            </select>
          )}
          {projects.length > 0 && (
            <select
              value={filterProject}
              onChange={(e) => setFilterProject(e.target.value)}
              className="w-full rounded border bg-background px-2 py-1 text-xs"
            >
              <option value="all">全プロジェクト</option>
              {projects.map((p) => (
                <option key={p.project_id} value={p.project_id}>{p.name}</option>
              ))}
            </select>
          )}
        </div>

        <p className="mb-1 px-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          レポート ({filtered.length})
        </p>

        {filtered.map((r) => (
          <div
            key={r.id}
            className={[
              "w-full rounded-lg px-3 py-2 text-left transition-colors",
              r.id === selectedId
                ? "bg-primary/10 ring-1 ring-inset ring-primary"
                : "hover:bg-muted",
            ].join(" ")}
          >
            <div className="flex items-start justify-between gap-1">
              <button onClick={() => setSelectedId(r.id)} className="min-w-0 flex-1 text-left">
                <span
                  className={`mb-1 inline-block rounded-full px-2 py-0.5 text-[10px] font-medium ${TYPE_COLOR[r.type]}`}
                >
                  {TYPE_LABEL[r.type]}
                </span>
                <p className="truncate text-xs font-medium leading-snug">{r.title}</p>
                <p className="mt-0.5 text-[10px] text-muted-foreground">{formatDate(r.createdAt)}</p>
              </button>
              <button
                onClick={() => handleDelete(r.id)}
                className="mt-0.5 shrink-0 rounded p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                aria-label="削除"
              >
                <Trash2 className="h-3 w-3" />
              </button>
            </div>

            {/* タグ付け */}
            <div className="mt-1.5 space-y-1">
              {members.length > 0 && r.type === "skill" && (
                <select
                  value={r.member_id ?? ""}
                  onChange={(e) => handleTag(r.id, "member_id", e.target.value || null)}
                  className="w-full rounded border bg-background px-1.5 py-0.5 text-[10px] text-muted-foreground"
                >
                  <option value="">メンバー未割当</option>
                  {members.map((m) => (
                    <option key={m.member_id} value={m.member_id}>{m.name}</option>
                  ))}
                </select>
              )}
              {projects.length > 0 && (
                <select
                  value={r.project_id ?? ""}
                  onChange={(e) => handleTag(r.id, "project_id", e.target.value || null)}
                  className="w-full rounded border bg-background px-1.5 py-0.5 text-[10px] text-muted-foreground"
                >
                  <option value="">プロジェクト未割当</option>
                  {projects.map((p) => (
                    <option key={p.project_id} value={p.project_id}>{p.name}</option>
                  ))}
                </select>
              )}
            </div>

            {r.type === "assignment" && (
              <button
                onClick={() => activeReportId === r.id ? clearActiveReport() : setActiveReport(r)}
                className={[
                  "mt-1.5 w-full rounded px-2 py-1 text-[10px] font-medium transition-colors",
                  activeReportId === r.id
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted hover:bg-primary/10 hover:text-primary",
                ].join(" ")}
              >
                {activeReportId === r.id ? "✓ 編集対象中" : "AIチャットで編集"}
              </button>
            )}
          </div>
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
            <div className="flex items-center gap-2">
              {diffAvailable && (
                <button
                  onClick={() => setShowDiff((v) => !v)}
                  className="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium transition-colors hover:bg-muted"
                >
                  {showDiff ? "差分を隠す" : "差分を見る"}
                </button>
              )}
              <button
                onClick={download}
                className="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium transition-colors hover:bg-muted"
              >
                <Download className="h-3.5 w-3.5" />
                ダウンロード
              </button>
            </div>
          </div>

          {/* コンテンツ */}
          <div className="flex-1 overflow-y-auto px-6 py-4">
            {showDiff && lastReportDiff && (
              <div className="mb-4">
                <p className="mb-1.5 text-xs font-semibold text-muted-foreground">変更差分</p>
                <RenderedDiffView before={lastReportDiff.before} after={lastReportDiff.after} />
              </div>
            )}
            <div className="markdown-body max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
                {selected.markdown}
              </ReactMarkdown>
            </div>
            <ChatHistorySection history={selected.chat_history ?? []} />
          </div>
        </div>
      ) : null}
    </div>
  );
}
