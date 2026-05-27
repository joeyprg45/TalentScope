"use client";

import { useState } from "react";
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

  // Build projectColorMap from all projects (stable ordering)
  const projectColorMap = new Map<string, string>();
  projects.forEach((p, i) => {
    projectColorMap.set(p.project_id, BAR_COLORS[i % BAR_COLORS.length]);
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

  // Build member rows with laned bars
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

  // Legend: only projects that have at least one assignment
  const legendProjects = projects.filter((p) =>
    members.some((m) => p.assignments?.some((a) => a.member_id === m.member_id)),
  );

  return (
    <div className="rounded-xl border bg-card shadow-sm">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b px-4 py-2.5">
        <span className="text-sm font-medium">全メンバータイムライン</span>
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

      {/* Gantt chart */}
      <div className="p-4">
        {members.length === 0 ? (
          <p className="py-6 text-center text-xs text-muted-foreground">
            メンバーデータなし
          </p>
        ) : (
          <div className="flex gap-0">
            {/* Name column */}
            <div className="w-24 shrink-0">
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
                    {bars.map(({ project, start, end, lane, totalLanes }) => {
                      const s = start < rangeStart ? rangeStart : start;
                      const e = end > rangeEnd ? rangeEnd : end;
                      const leftPct = toPercent(s);
                      const widthPct = clamp(toPercent(e) - leftPct, 0.5, 100);
                      if (widthPct <= 0) return null;
                      const color =
                        projectColorMap.get(project.project_id) ?? BAR_COLORS[0];
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
        )}

        {/* Legend */}
        {legendProjects.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 border-t pt-3">
            {legendProjects.map((p, i) => (
              <div key={p.project_id} className="flex items-center gap-1.5">
                <div
                  className="h-2.5 w-2.5 rounded-sm"
                  style={{ backgroundColor: BAR_COLORS_HEX[i % BAR_COLORS_HEX.length] }}
                />
                <span className="text-[11px] text-muted-foreground">{p.name}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
