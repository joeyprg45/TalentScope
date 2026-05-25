"use client";

import { Folder, X } from "lucide-react";
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

type Props = {
  projects: Project[];
  members: Member[];
  selectedMemberIds: string[];
  onMemberToggle: (id: string) => void;
  groupProjectId: string | null;
  onGroupProjectAdd: (id: string) => void;
  onGroupProjectClear: () => void;
  rangeStart: string;
  rangeEnd: string;
  onRangeChange: (start: string, end: string) => void;
};

function clamp(val: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, val));
}

function toLocalDateStr(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function MemberTimeline({
  projects,
  members,
  selectedMemberIds,
  onMemberToggle,
  groupProjectId,
  onGroupProjectAdd,
  onGroupProjectClear,
  rangeStart,
  rangeEnd,
  onRangeChange,
}: Props) {
  const now = new Date();
  const todayStr = toLocalDateStr(now);
  const currentYear = now.getFullYear();
  const currentMonthIdx = now.getMonth();

  const rangeDays = Math.max(
    1,
    (new Date(rangeEnd).getTime() - new Date(rangeStart).getTime()) / 86400000,
  );

  function toPercent(dateStr: string): number {
    const ms = new Date(dateStr).getTime() - new Date(rangeStart).getTime();
    return clamp((ms / 86400000 / rangeDays) * 100, 0, 100);
  }

  const setThisYear = () =>
    onRangeChange(`${currentYear}-01-01`, `${currentYear}-12-31`);

  const setThisMonth = () => {
    const mm = String(currentMonthIdx + 1).padStart(2, "0");
    const lastDay = new Date(currentYear, currentMonthIdx + 1, 0).getDate();
    onRangeChange(
      `${currentYear}-${mm}-01`,
      `${currentYear}-${mm}-${String(lastDay).padStart(2, "0")}`,
    );
  };

  const set3Months = () => {
    const start = new Date(now);
    start.setMonth(start.getMonth() - 1);
    const end = new Date(now);
    end.setMonth(end.getMonth() + 2);
    onRangeChange(toLocalDateStr(start), toLocalDateStr(end));
  };

  // Proportional month axis labels
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

  const groupProject = projects.find((p) => p.project_id === groupProjectId) ?? null;

  const displayMembers = members.filter((mem) =>
    selectedMemberIds.includes(mem.member_id),
  );

  const memberRows = displayMembers.map((member) => {
    const bars = projects
      .filter((p) => p.assignments?.some((a) => a.member_id === member.member_id))
      .map((p) => {
        const a = p.assignments!.find((a) => a.member_id === member.member_id)!;
        return {
          project: p,
          start: a.start ?? p.period?.start ?? rangeStart,
          end: a.end ?? p.period?.end ?? rangeEnd,
        };
      });
    return { member, bars };
  });

  const projectColorMap = new Map<string, string>();
  let colorIdx = 0;
  memberRows.forEach(({ bars }) => {
    bars.forEach(({ project }) => {
      if (!projectColorMap.has(project.project_id)) {
        projectColorMap.set(
          project.project_id,
          BAR_COLORS[colorIdx % BAR_COLORS.length],
        );
        colorIdx++;
      }
    });
  });

  const projBand =
    groupProject?.period
      ? (() => {
          const l = toPercent(groupProject.period.start);
          const r = toPercent(groupProject.period.end);
          return { left: l, width: clamp(r - l, 1, 100) };
        })()
      : null;

  const isEmpty = displayMembers.length === 0;

  return (
    <div className="rounded-xl border bg-card shadow-sm">
      {/* ── Controls bar ─────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-2 border-b px-4 py-2.5">
        <div className="flex items-center gap-1.5">
          <input
            type="date"
            value={rangeStart}
            onChange={(e) => onRangeChange(e.target.value, rangeEnd)}
            className="rounded border bg-background px-2 py-0.5 text-xs"
          />
          <span className="text-xs text-muted-foreground">〜</span>
          <input
            type="date"
            value={rangeEnd}
            onChange={(e) => onRangeChange(rangeStart, e.target.value)}
            className="rounded border bg-background px-2 py-0.5 text-xs"
          />
        </div>
        <div className="flex gap-1">
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

      {/* ── Selector row ─────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-1.5 border-b px-4 py-2">
        {/* Individual member chips */}
        {members.length === 0 ? (
          <span className="text-xs text-muted-foreground">メンバーデータなし</span>
        ) : (
          members.map((mem) => {
            const selected = selectedMemberIds.includes(mem.member_id);
            return (
              <button
                key={mem.member_id}
                onClick={() => onMemberToggle(mem.member_id)}
                className={[
                  "flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium transition-colors",
                  selected
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:bg-muted/70",
                ].join(" ")}
              >
                {mem.name}
                {selected && <X className="h-3 w-3" />}
              </button>
            );
          })
        )}

        {/* Divider */}
        <div className="mx-1 h-4 w-px bg-border" />

        {/* Group (project) bulk-add dropdown */}
        <Folder className="h-3.5 w-3.5 shrink-0 text-indigo-500" />
        <select
          value=""
          onChange={(e) => {
            if (e.target.value) onGroupProjectAdd(e.target.value);
          }}
          className="rounded-md border bg-background px-2 py-0.5 text-xs text-muted-foreground"
        >
          <option value="">グループから追加...</option>
          {projects.map((p) => (
            <option key={p.project_id} value={p.project_id}>
              {p.name}
            </option>
          ))}
        </select>

        {/* Group badge (shown when a project was bulk-added) */}
        {groupProject && (
          <span className="flex items-center gap-1 rounded-full bg-indigo-100 px-2.5 py-0.5 text-xs font-medium text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300">
            <Folder className="h-3 w-3" />
            {groupProject.name}
            <button
              onClick={onGroupProjectClear}
              className="ml-0.5 rounded-full hover:text-indigo-900 dark:hover:text-indigo-100"
              aria-label="グループ表示を解除"
            >
              <X className="h-3 w-3" />
            </button>
          </span>
        )}
      </div>

      {/* ── Gantt chart ──────────────────────────────────────────── */}
      <div className="p-4">
        {isEmpty ? (
          <p className="py-6 text-center text-xs text-muted-foreground">
            上のチップでメンバーを選択するか、グループから一括追加してください
          </p>
        ) : (
          <div className="flex gap-0">
            {/* Name column */}
            <div className="w-20 shrink-0">
              <div className="mb-1 h-5" />
              {memberRows.map(({ member }) => (
                <div
                  key={member.member_id}
                  className="mb-2 flex h-5 items-center truncate text-[11px] font-medium"
                >
                  {member.name}
                </div>
              ))}
            </div>

            {/* Gantt area */}
            <div className="min-w-0 flex-1 overflow-hidden">
              {/* Month axis */}
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

              {/* Rows + overlays */}
              <div className="relative">
                {/* Project period band (group indicator) */}
                {projBand && (
                  <div
                    className="pointer-events-none absolute bottom-0 top-0 z-0 border-x border-indigo-300/50 bg-indigo-400/10"
                    style={{ left: `${projBand.left}%`, width: `${projBand.width}%` }}
                  />
                )}

                {/* Today marker */}
                {todayPct !== null && (
                  <div
                    className="pointer-events-none absolute bottom-0 top-0 z-20 w-px bg-red-500/70"
                    style={{ left: `${todayPct}%` }}
                  >
                    <div className="absolute top-0 h-2 w-2 -translate-x-[3px] rounded-full bg-red-500" />
                  </div>
                )}

                {/* Member bar rows */}
                {memberRows.map(({ member, bars }) => (
                  <div
                    key={member.member_id}
                    className="relative z-10 mb-2 h-5 w-full rounded bg-muted"
                  >
                    {bars.map(({ project, start, end }) => {
                      const s = start < rangeStart ? rangeStart : start;
                      const e = end > rangeEnd ? rangeEnd : end;
                      const leftPct = toPercent(s);
                      const widthPct = clamp(toPercent(e) - leftPct, 0.5, 100);
                      if (widthPct <= 0) return null;
                      const color =
                        projectColorMap.get(project.project_id) ?? BAR_COLORS[0];
                      return (
                        <div
                          key={project.project_id}
                          className={`absolute h-full cursor-default rounded opacity-80 transition-opacity hover:opacity-100 ${color}`}
                          style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
                          title={`${member.name} / ${project.name}\n開始: ${start}  終了: ${end}`}
                        />
                      );
                    })}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
