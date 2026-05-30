"use client";

import { useState, useRef, useEffect } from "react";
import type { Member, Project } from "@/lib/types";

const BAR_COLORS = [
  "bg-blue-400",
  "bg-emerald-400",
  "bg-violet-400",
  "bg-amber-400",
  "bg-rose-400",
  "bg-cyan-400",
  "bg-orange-400",
];

const BAR_COLORS_HEX = [
  "#60a5fa",
  "#34d399",
  "#a78bfa",
  "#fbbf24",
  "#fb7185",
  "#22d3ee",
  "#fb923c",
];

type Props = {
  members: Member[];
  projects: Project[];
};

type LanedBar = {
  project: Project;
  start: string;
  end: string;
  lane: number;
  totalLanes: number;
};

function clamp(val: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, val));
}

function toLocalDateStr(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function computeLanes(
  rawBars: { project: Project; start: string; end: string }[],
): LanedBar[] {
  const sorted = [...rawBars].sort((a, b) => a.start.localeCompare(b.start));
  const laneEnds: string[] = [];

  const result = sorted.map((bar) => {
    let lane = laneEnds.findIndex((endDate) => endDate <= bar.start);
    if (lane === -1) {
      lane = laneEnds.length;
      laneEnds.push(bar.end);
    } else {
      laneEnds[lane] = bar.end;
    }
    return { ...bar, lane, totalLanes: -1 };
  });

  const totalLanes = Math.max(1, laneEnds.length);
  return result.map((b) => ({ ...b, totalLanes }));
}

export function HomeMemberTimeline({ members, projects }: Props) {
  const now = new Date();
  const currentYear = now.getFullYear();
  const todayStr = toLocalDateStr(now);

  const [rangeStart, setRangeStart] = useState(`${currentYear}-01-01`);
  const [rangeEnd, setRangeEnd] = useState(`${currentYear}-12-31`);
  const [viewMode, setViewMode] = useState<"project" | "member">("project");
  const [expandedProjects, setExpandedProjects] = useState<Set<string>>(new Set());

  // メンバー選択UI
  const [selectedMemberIds, setSelectedMemberIds] = useState<Set<string>>(
    () => new Set(members.map((m) => m.member_id)),
  );
  const [memberSearch, setMemberSearch] = useState("");
  const [showSelector, setShowSelector] = useState(false);
  const selectorRef = useRef<HTMLDivElement>(null);

  // membersが更新されたとき、新規メンバーを自動的に選択状態にする
  useEffect(() => {
    setSelectedMemberIds((prev) => {
      const next = new Set(prev);
      let changed = false;
      members.forEach((m) => {
        if (!next.has(m.member_id)) {
          next.add(m.member_id);
          changed = true;
        }
      });
      return changed ? next : prev;
    });
  }, [members]);

  // ドロップダウン外クリックで閉じる
  useEffect(() => {
    if (!showSelector) return;
    const handler = (e: MouseEvent) => {
      if (selectorRef.current && !selectorRef.current.contains(e.target as Node)) {
        setShowSelector(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showSelector]);

  const rangeDays = Math.max(
    1,
    (new Date(rangeEnd).getTime() - new Date(rangeStart).getTime()) / 86400000,
  );

  function toPercent(dateStr: string): number {
    const ms = new Date(dateStr).getTime() - new Date(rangeStart).getTime();
    return clamp((ms / 86400000 / rangeDays) * 100, 0, 100);
  }

  const setThisYear = () => {
    setRangeStart(`${currentYear}-01-01`);
    setRangeEnd(`${currentYear}-12-31`);
  };

  const setThisMonth = () => {
    const mm = String(now.getMonth() + 1).padStart(2, "0");
    const lastDay = new Date(currentYear, now.getMonth() + 1, 0).getDate();
    setRangeStart(`${currentYear}-${mm}-01`);
    setRangeEnd(`${currentYear}-${mm}-${String(lastDay).padStart(2, "0")}`);
  };

  const set3Months = () => {
    const start = new Date(now);
    start.setMonth(start.getMonth() - 1);
    const end = new Date(now);
    end.setMonth(end.getMonth() + 2);
    setRangeStart(toLocalDateStr(start));
    setRangeEnd(toLocalDateStr(end));
  };

  // stable color index by original projects array order
  const projectColorMap = new Map<string, { tailwind: string; hex: string }>();
  projects.forEach((p, i) => {
    projectColorMap.set(p.project_id, {
      tailwind: BAR_COLORS[i % BAR_COLORS.length],
      hex: BAR_COLORS_HEX[i % BAR_COLORS_HEX.length],
    });
  });

  // Month axis labels
  const monthLabels: { label: string; pct: number }[] = [];
  {
    const startDate = new Date(rangeStart);
    const endDate = new Date(rangeEnd);
    let cursor = new Date(startDate.getFullYear(), startDate.getMonth(), 1);
    while (cursor <= endDate) {
      monthLabels.push({
        label: `${cursor.getMonth() + 1}月`,
        pct: toPercent(toLocalDateStr(cursor)),
      });
      cursor = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1);
    }
  }

  const todayPct =
    todayStr >= rangeStart && todayStr <= rangeEnd ? toPercent(todayStr) : null;

  const MIN_PX_PER_DAY = 3;
  const ganttPxWidth = Math.max(600, rangeDays * MIN_PX_PER_DAY);

  const toggleProject = (projectId: string) => {
    setExpandedProjects((prev) => {
      const next = new Set(prev);
      if (next.has(projectId)) next.delete(projectId);
      else next.add(projectId);
      return next;
    });
  };

  // ── Project view rows ──────────────────────────────────────────
  const assignedProjects = projects;

  type ProjectRow =
    | { type: "project"; project: Project }
    | { type: "member"; member: Member; project: Project };

  const projectRows: ProjectRow[] = [];
  for (const project of assignedProjects) {
    projectRows.push({ type: "project", project });
    if (expandedProjects.has(project.project_id)) {
      const assignedMembers = members.filter((m) =>
        project.assignments?.some((a) => a.member_id === m.member_id),
      );
      for (const member of assignedMembers) {
        projectRows.push({ type: "member", member, project });
      }
    }
  }

  // ── Member selector helpers ─────────────────────────────────────
  const filteredSelectorMembers = members.filter((m) => {
    const q = memberSearch.toLowerCase();
    return (
      m.name.toLowerCase().includes(q) ||
      (m.role ?? "").toLowerCase().includes(q)
    );
  });

  const toggleMember = (id: string) => {
    setSelectedMemberIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAll = () => setSelectedMemberIds(new Set(members.map((m) => m.member_id)));
  const clearAll = () => setSelectedMemberIds(new Set());

  // ── Member view rows ───────────────────────────────────────────
  const memberRows = members.map((member) => {
    const rawBars = projects
      .filter((p) => p.assignments?.some((a) => a.member_id === member.member_id))
      .map((p) => {
        const a = p.assignments!.find((a) => a.member_id === member.member_id)!;
        return {
          project: p,
          start: a.start ?? p.period?.start ?? rangeStart,
          end: a.end ?? p.period?.end ?? rangeEnd,
        };
      });
    return { member, bars: computeLanes(rawBars) };
  });

  const displayedMemberRows = memberRows.filter(({ member }) =>
    selectedMemberIds.has(member.member_id),
  );

  const legendProjects = projects.filter((p) =>
    members.some((m) => p.assignments?.some((a) => a.member_id === m.member_id)),
  );

  return (
    <div className="rounded-xl border bg-card shadow-sm">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b px-4 py-2.5">
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium">
            {viewMode === "project" ? "プロジェクトタイムライン" : "メンバー別タイムライン"}
          </span>
          {/* View toggle */}
          <div className="flex items-center gap-0.5 rounded-full border px-0.5 py-0.5 text-[11px]">
            <button
              onClick={() => setViewMode("project")}
              className={`rounded-full px-2 py-0.5 transition-colors ${
                viewMode === "project"
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              PJ別
            </button>
            <button
              onClick={() => setViewMode("member")}
              className={`rounded-full px-2 py-0.5 transition-colors ${
                viewMode === "member"
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              メンバー別
            </button>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-1">
          {/* 日付範囲入力 */}
          <div className="flex items-center gap-1">
            <input
              type="date"
              value={rangeStart}
              onChange={(e) => e.target.value && setRangeStart(e.target.value)}
              className="rounded border px-1.5 py-0.5 text-xs text-foreground outline-none focus:ring-1 focus:ring-primary"
            />
            <span className="text-xs text-muted-foreground">〜</span>
            <input
              type="date"
              value={rangeEnd}
              onChange={(e) => e.target.value && setRangeEnd(e.target.value)}
              className="rounded border px-1.5 py-0.5 text-xs text-foreground outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
          <span className="text-muted-foreground/40 text-xs">|</span>
          {/* メンバー選択ドロップダウン（メンバー別ビューのみ） */}
          {viewMode === "member" && (
            <div className="relative" ref={selectorRef}>
              <button
                onClick={() => setShowSelector((v) => !v)}
                className="flex items-center gap-1 rounded border px-2 py-0.5 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                <span>
                  メンバー ({selectedMemberIds.size}/{members.length})
                </span>
                <span className="text-[9px]">{showSelector ? "▲" : "▼"}</span>
              </button>

              {showSelector && (
                <div className="absolute left-0 top-full z-50 mt-1 w-56 rounded-lg border bg-card shadow-lg">
                  {/* 検索 */}
                  <div className="border-b p-2">
                    <input
                      type="text"
                      value={memberSearch}
                      onChange={(e) => setMemberSearch(e.target.value)}
                      placeholder="名前・ロールで検索"
                      className="w-full rounded border px-2 py-1 text-xs outline-none focus:ring-1 focus:ring-primary"
                    />
                  </div>
                  {/* 全選択/全解除 */}
                  <div className="flex gap-1 border-b px-2 py-1.5">
                    <button
                      onClick={selectAll}
                      className="rounded border px-2 py-0.5 text-[11px] text-muted-foreground hover:bg-muted hover:text-foreground"
                    >
                      全選択
                    </button>
                    <button
                      onClick={clearAll}
                      className="rounded border px-2 py-0.5 text-[11px] text-muted-foreground hover:bg-muted hover:text-foreground"
                    >
                      全解除
                    </button>
                  </div>
                  {/* メンバーリスト */}
                  <div className="max-h-64 overflow-y-auto">
                    {filteredSelectorMembers.length === 0 ? (
                      <p className="py-3 text-center text-[11px] text-muted-foreground">
                        該当なし
                      </p>
                    ) : (
                      filteredSelectorMembers.map((m) => (
                        <label
                          key={m.member_id}
                          className="flex cursor-pointer items-center gap-2 px-3 py-1.5 hover:bg-muted/60"
                        >
                          <input
                            type="checkbox"
                            checked={selectedMemberIds.has(m.member_id)}
                            onChange={() => toggleMember(m.member_id)}
                            className="h-3.5 w-3.5 shrink-0 accent-primary"
                          />
                          <div className="min-w-0">
                            <p className="truncate text-[12px] font-medium">{m.name}</p>
                            {m.role && (
                              <p className="truncate text-[10px] text-muted-foreground">
                                {m.role}
                              </p>
                            )}
                          </div>
                        </label>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {[
            { label: "今年", fn: setThisYear },
            { label: "今月", fn: setThisMonth },
            { label: "3ヶ月", fn: set3Months },
          ].map(({ label, fn }) => (
            <button
              key={label}
              onClick={fn}
              className="rounded border px-2 py-0.5 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Gantt chart */}
      <div className="p-4">
        {viewMode === "project" ? (
          /* ── Project view ── */
          assignedProjects.length === 0 ? (
            <p className="py-6 text-center text-xs text-muted-foreground">
              プロジェクトデータなし
            </p>
          ) : (
            <div className="overflow-x-auto">
              <div className="flex" style={{ minWidth: `${160 + ganttPxWidth}px` }}>
                {/* Name column - sticky */}
                <div className="sticky left-0 z-30 bg-card w-40 shrink-0 border-r">
                  <div className="mb-1 h-5" />
                  {projectRows.map((row) => {
                    if (row.type === "project") {
                      const isExpanded = expandedProjects.has(row.project.project_id);
                      const color = projectColorMap.get(row.project.project_id);
                      return (
                        <div
                          key={`label-proj-${row.project.project_id}`}
                          className="mb-1 flex h-7 cursor-pointer select-none items-center gap-1.5 rounded px-1 text-[11px] font-semibold hover:bg-muted/60"
                          onClick={() => toggleProject(row.project.project_id)}
                        >
                          <span
                            className="h-2.5 w-2.5 shrink-0 rounded-sm"
                            style={{ backgroundColor: color?.hex }}
                          />
                          <span className="flex-1 truncate">{row.project.name}</span>
                          <span className="shrink-0 text-[9px] text-muted-foreground">
                            {isExpanded ? "▼" : "▶"}
                          </span>
                        </div>
                      );
                    } else {
                      return (
                        <div
                          key={`label-mem-${row.project.project_id}-${row.member.member_id}`}
                          className="mb-1 flex h-3 items-center pl-5"
                        >
                          <span className="truncate text-[9px] text-muted-foreground">
                            {row.member.name}
                          </span>
                        </div>
                      );
                    }
                  })}
                </div>

                {/* Gantt area - fixed pixel width */}
                <div style={{ width: `${ganttPxWidth}px`, flexShrink: 0 }}>
                  <div className="relative mb-1 h-5">
                    {monthLabels.map(({ label, pct }, i) => (
                      <span
                        key={`${label}-${i}`}
                        className="absolute -translate-x-1/2 select-none text-[9px] text-muted-foreground"
                        style={{ left: `${pct}%` }}
                      >
                        {label}
                      </span>
                    ))}
                  </div>

                  <div className="relative">
                    {todayPct !== null && (
                      <div
                        className="pointer-events-none absolute bottom-0 top-0 z-20 w-px bg-red-500/70"
                        style={{ left: `${todayPct}%` }}
                      >
                        <div className="absolute top-0 h-2 w-2 -translate-x-[3px] rounded-full bg-red-500" />
                      </div>
                    )}

                    {projectRows.map((row) => {
                      if (row.type === "project") {
                        const color = projectColorMap.get(row.project.project_id);
                        const start = row.project.period?.start ?? rangeStart;
                        const end = row.project.period?.end ?? rangeEnd;
                        const s = start < rangeStart ? rangeStart : start;
                        const e = end > rangeEnd ? rangeEnd : end;
                        const leftPct = toPercent(s);
                        const widthPct = clamp(toPercent(e) - leftPct, 0.5, 100);
                        return (
                          <div
                            key={`bar-proj-${row.project.project_id}`}
                            className="relative mb-1 h-7 w-full cursor-pointer rounded bg-muted/40 hover:bg-muted/60"
                            onClick={() => toggleProject(row.project.project_id)}
                          >
                            {widthPct > 0 && (
                              <div
                                className={`absolute h-full rounded opacity-75 transition-opacity hover:opacity-95 ${color?.tailwind ?? BAR_COLORS[0]}`}
                                style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
                                title={`${row.project.name}  ${start} 〜 ${end}`}
                              />
                            )}
                          </div>
                        );
                      } else {
                        const a = row.project.assignments!.find(
                          (a) => a.member_id === row.member.member_id,
                        )!;
                        const start = a.start ?? row.project.period?.start ?? rangeStart;
                        const end = a.end ?? row.project.period?.end ?? rangeEnd;
                        const s = start < rangeStart ? rangeStart : start;
                        const e = end > rangeEnd ? rangeEnd : end;
                        const leftPct = toPercent(s);
                        const widthPct = clamp(toPercent(e) - leftPct, 0.5, 100);
                        const color = projectColorMap.get(row.project.project_id);
                        return (
                          <div
                            key={`bar-mem-${row.project.project_id}-${row.member.member_id}`}
                            className="relative mb-1 h-3 w-full rounded bg-muted/20"
                          >
                            {widthPct > 0 && (
                              <div
                                className={`absolute h-full rounded opacity-40 ${color?.tailwind ?? BAR_COLORS[0]}`}
                                style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
                                title={`${row.member.name} / ${row.project.name}  ${start} 〜 ${end}`}
                              />
                            )}
                          </div>
                        );
                      }
                    })}
                  </div>
                </div>
              </div>
            </div>
          )
        ) : (
          /* ── Member view ── */
          members.length === 0 ? (
            <p className="py-6 text-center text-xs text-muted-foreground">
              メンバーデータなし
            </p>
          ) : displayedMemberRows.length === 0 ? (
            <p className="py-6 text-center text-xs text-muted-foreground">
              メンバーが選択されていません
            </p>
          ) : (
            <div className="overflow-x-auto">
              <div className="flex" style={{ minWidth: `${96 + ganttPxWidth}px` }}>
                {/* Name column - sticky */}
                <div className="sticky left-0 z-30 bg-card w-24 shrink-0 border-r">
                  <div className="mb-1 h-5" />
                  {displayedMemberRows.map(({ member }) => (
                    <div
                      key={member.member_id}
                      className="mb-2 flex h-5 items-center truncate text-[11px] font-medium"
                    >
                      {member.name}
                    </div>
                  ))}
                </div>

                {/* Gantt area - fixed pixel width */}
                <div style={{ width: `${ganttPxWidth}px`, flexShrink: 0 }}>
                  <div className="relative mb-1 h-5">
                    {monthLabels.map(({ label, pct }, i) => (
                      <span
                        key={`${label}-${i}`}
                        className="absolute -translate-x-1/2 select-none text-[9px] text-muted-foreground"
                        style={{ left: `${pct}%` }}
                      >
                        {label}
                      </span>
                    ))}
                  </div>

                  <div className="relative">
                    {todayPct !== null && (
                      <div
                        className="pointer-events-none absolute bottom-0 top-0 z-20 w-px bg-red-500/70"
                        style={{ left: `${todayPct}%` }}
                      >
                        <div className="absolute top-0 h-2 w-2 -translate-x-[3px] rounded-full bg-red-500" />
                      </div>
                    )}

                    {displayedMemberRows.map(({ member, bars }) => (
                      <div
                        key={member.member_id}
                        className="relative z-10 mb-2 h-5 w-full rounded bg-muted"
                      >
                        {bars.map(({ project, start, end, lane, totalLanes }) => {
                          const s = start < rangeStart ? rangeStart : start;
                          const e = end > rangeEnd ? rangeEnd : end;
                          const leftPct = toPercent(s);
                          const widthPct = clamp(toPercent(e) - leftPct, 0.5, 100);
                          if (widthPct <= 0) return null;
                          const color =
                            projectColorMap.get(project.project_id)?.tailwind ?? BAR_COLORS[0];
                          const topPct = (lane / totalLanes) * 100;
                          const heightPct = (1 / totalLanes) * 100;
                          return (
                            <div
                              key={project.project_id}
                              className={`absolute cursor-default rounded opacity-80 transition-opacity hover:opacity-100 ${color}`}
                              style={{
                                left: `${leftPct}%`,
                                width: `${widthPct}%`,
                                top: `${topPct}%`,
                                height: `${heightPct}%`,
                              }}
                              title={`${member.name} / ${project.name}\n開始: ${start}  終了: ${end}`}
                            />
                          );
                        })}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )
        )}

        {/* Legend */}
        {legendProjects.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 border-t pt-3">
            {legendProjects.map((p) => {
              const color = projectColorMap.get(p.project_id);
              return (
                <div key={p.project_id} className="flex items-center gap-1.5">
                  <div
                    className="h-2.5 w-2.5 rounded-sm"
                    style={{ backgroundColor: color?.hex }}
                  />
                  <span className="text-[11px] text-muted-foreground">{p.name}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
