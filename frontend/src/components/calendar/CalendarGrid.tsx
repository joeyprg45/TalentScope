"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import type { Project } from "@/lib/types";

const WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"];

const TODAY = new Date();
const TODAY_STR = toDateString(TODAY.getFullYear(), TODAY.getMonth() + 1, TODAY.getDate());

function toDateString(y: number, m: number, d: number): string {
  return `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

function buildCalendarDays(year: number, month: number): (number | null)[] {
  const firstDay = new Date(year, month - 1, 1).getDay();
  const offset = firstDay === 0 ? 6 : firstDay - 1; // 月曜始まり
  const daysInMonth = new Date(year, month, 0).getDate();
  const cells: (number | null)[] = Array(offset).fill(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);
  while (cells.length % 7 !== 0) cells.push(null);
  return cells;
}

function getDayEvents(
  projects: Project[],
  dateStr: string,
): { starts: Project[]; ends: Project[] } {
  return {
    starts: projects.filter((p) => p.period?.start === dateStr),
    ends: projects.filter((p) => p.period?.end === dateStr),
  };
}

type Props = {
  projects: Project[];
  currentMonth: Date;
  selectedDate: string | null;
  onDayClick: (date: string) => void;
  onMonthChange: (d: Date) => void;
};

export function CalendarGrid({
  projects,
  currentMonth,
  selectedDate,
  onDayClick,
  onMonthChange,
}: Props) {
  const year = currentMonth.getFullYear();
  const month = currentMonth.getMonth() + 1;
  const cells = buildCalendarDays(year, month);

  const prevMonth = () => {
    const d = new Date(year, month - 2, 1);
    onMonthChange(d);
  };
  const nextMonth = () => {
    const d = new Date(year, month, 1);
    onMonthChange(d);
  };

  return (
    <div className="rounded-xl border bg-card shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-3">
        <button
          onClick={prevMonth}
          className="rounded p-1 hover:bg-muted transition-colors"
          aria-label="前月"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <span className="font-semibold text-sm">
          {year}年{month}月
        </span>
        <button
          onClick={nextMonth}
          className="rounded p-1 hover:bg-muted transition-colors"
          aria-label="次月"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>

      {/* Weekday labels */}
      <div className="grid grid-cols-7 border-b text-center text-[11px] font-medium text-muted-foreground">
        {WEEKDAYS.map((w) => (
          <div key={w} className="py-1.5">
            {w}
          </div>
        ))}
      </div>

      {/* Day cells */}
      <div className="grid grid-cols-7">
        {cells.map((day, idx) => {
          if (day === null) {
            return <div key={`empty-${idx}`} className="min-h-[72px] border-b border-r last:border-r-0" />;
          }
          const dateStr = toDateString(year, month, day);
          const { starts, ends } = getDayEvents(projects, dateStr);
          const isToday = dateStr === TODAY_STR;
          const isSelected = dateStr === selectedDate;

          return (
            <button
              key={dateStr}
              onClick={() => onDayClick(dateStr)}
              className={[
                "relative min-h-[72px] border-b border-r p-1 text-left transition-colors hover:bg-muted/50",
                // last col in each row has no right border
                (idx + 1) % 7 === 0 ? "border-r-0" : "",
                isSelected ? "bg-primary/10 ring-1 ring-inset ring-primary" : "",
              ].join(" ")}
            >
              <span
                className={[
                  "inline-flex h-5 w-5 items-center justify-center rounded-full text-[11px] font-medium",
                  isToday ? "bg-primary text-primary-foreground" : "text-foreground",
                ].join(" ")}
              >
                {day}
              </span>

              {/* Start badges */}
              <div className="mt-0.5 space-y-0.5">
                {starts.map((p) => (
                  <div
                    key={`s-${p.project_id}`}
                    className="flex items-center gap-0.5 rounded bg-primary/15 px-1 py-0.5 text-[9px] font-medium text-primary"
                    title={`${p.name} 開始`}
                  >
                    <span>▶</span>
                    <span className="truncate max-w-[56px]">{p.name}</span>
                  </div>
                ))}
                {/* End badges */}
                {ends.map((p) => (
                  <div
                    key={`e-${p.project_id}`}
                    className="flex items-center gap-0.5 rounded bg-muted px-1 py-0.5 text-[9px] font-medium text-muted-foreground"
                    title={`${p.name} 終了`}
                  >
                    <span className="truncate max-w-[56px]">{p.name}</span>
                    <span>◀</span>
                  </div>
                ))}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
