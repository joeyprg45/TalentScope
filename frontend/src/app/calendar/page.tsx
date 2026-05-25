"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Member, Project } from "@/lib/types";
import { CalendarGrid } from "@/components/calendar/CalendarGrid";
import { DayDetail } from "@/components/calendar/DayDetail";
import { MemberTimeline } from "@/components/calendar/MemberTimeline";

export default function CalendarPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [currentMonth, setCurrentMonth] = useState(() => new Date());
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [selectedMemberIds, setSelectedMemberIds] = useState<string[]>([]);
  const [groupProjectId, setGroupProjectId] = useState<string | null>(null);
  const [rangeStart, setRangeStart] = useState<string>(
    `${new Date().getFullYear()}-01-01`,
  );
  const [rangeEnd, setRangeEnd] = useState<string>(
    `${new Date().getFullYear()}-12-31`,
  );

  useEffect(() => {
    Promise.all([api.projects(), api.members()])
      .then(([ps, ms]) => {
        setProjects(ps);
        setMembers(ms);
      })
      .finally(() => setLoading(false));
  }, []);

  const toggleMember = useCallback((id: string) => {
    setSelectedMemberIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  }, []);

  const handleGroupProjectAdd = useCallback(
    (projectId: string) => {
      const project = projects.find((p) => p.project_id === projectId);
      if (!project) return;
      const newIds = project.assignments?.map((a) => a.member_id) ?? [];
      setSelectedMemberIds((prev) => {
        const merged = [...prev];
        newIds.forEach((id) => {
          if (!merged.includes(id)) merged.push(id);
        });
        return merged;
      });
      setGroupProjectId(projectId);
    },
    [projects],
  );

  const handleGroupProjectClear = useCallback(() => setGroupProjectId(null), []);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground text-sm">
        読み込み中…
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col gap-4 overflow-auto p-4">
      {/* 上: メンバータイムライン（全幅） */}
      <MemberTimeline
        projects={projects}
        members={members}
        selectedMemberIds={selectedMemberIds}
        onMemberToggle={toggleMember}
        groupProjectId={groupProjectId}
        onGroupProjectAdd={handleGroupProjectAdd}
        onGroupProjectClear={handleGroupProjectClear}
        rangeStart={rangeStart}
        rangeEnd={rangeEnd}
        onRangeChange={(s, e) => {
          setRangeStart(s);
          setRangeEnd(e);
        }}
      />
      {/* 下: カレンダー + 日付詳細 */}
      <div className="flex flex-col gap-3">
        <CalendarGrid
          projects={projects}
          currentMonth={currentMonth}
          selectedDate={selectedDate}
          onDayClick={setSelectedDate}
          onMonthChange={setCurrentMonth}
        />
        {selectedDate && (
          <DayDetail projects={projects} date={selectedDate} />
        )}
      </div>
    </div>
  );
}
