"use client";

import { useEffect, useState } from "react";
import { CalendarRange, CheckCircle2, Circle, Clock, Users } from "lucide-react";
import { api } from "@/lib/api";
import type { Member, Project } from "@/lib/types";

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.projects(), api.members()])
      .then(([p, m]) => {
        setProjects(p);
        setMembers(m);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  const memberMap = Object.fromEntries(members.map((m) => [m.member_id, m]));

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground text-sm">
        読み込み中…
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full items-center justify-center text-destructive text-sm">
        エラー: {error}
      </div>
    );
  }

  const active = projects.filter((p) => p.status === "active");
  const planning = projects.filter((p) => p.status === "planning");
  const others = projects.filter((p) => p.status !== "active" && p.status !== "planning");

  return (
    <div className="h-full overflow-y-auto p-6 space-y-8">
      <div>
        <h1 className="text-2xl font-bold">プロジェクト</h1>
        <p className="mt-1 text-sm text-muted-foreground">{projects.length} 件登録</p>
      </div>

      <Section title="進行中" icon={<Circle className="h-4 w-4 fill-green-500 text-green-500" />} projects={active} memberMap={memberMap} />
      <Section title="計画中" icon={<Clock className="h-4 w-4 text-yellow-500" />} projects={planning} memberMap={memberMap} />
      {others.length > 0 && (
        <Section title="その他" icon={<CheckCircle2 className="h-4 w-4 text-muted-foreground" />} projects={others} memberMap={memberMap} />
      )}
    </div>
  );
}

function Section({
  title,
  icon,
  projects,
  memberMap,
}: {
  title: string;
  icon: React.ReactNode;
  projects: Project[];
  memberMap: Record<string, Member>;
}) {
  if (projects.length === 0) return null;
  return (
    <div className="space-y-3">
      <h2 className="flex items-center gap-2 text-sm font-semibold text-muted-foreground">
        {icon}
        {title}
        <span className="ml-1 rounded-full bg-muted px-2 py-0.5 text-xs">{projects.length}</span>
      </h2>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {projects.map((p) => (
          <ProjectCard key={p.project_id} project={p} memberMap={memberMap} />
        ))}
      </div>
    </div>
  );
}

const STATUS_LABEL: Record<string, string> = {
  active: "進行中",
  planning: "計画中",
  completed: "完了",
  on_hold: "保留",
};

const STATUS_COLOR: Record<string, string> = {
  active: "bg-green-100 text-green-700",
  planning: "bg-yellow-100 text-yellow-700",
  completed: "bg-muted text-muted-foreground",
  on_hold: "bg-orange-100 text-orange-700",
};

function formatDate(d?: string | null) {
  if (!d) return "?";
  return new Date(d).toLocaleDateString("ja-JP", { year: "numeric", month: "short", day: "numeric" });
}

function daysLeft(end?: string | null) {
  if (!end) return null;
  const diff = new Date(end).getTime() - Date.now();
  const days = Math.ceil(diff / (1000 * 60 * 60 * 24));
  return days;
}

function ProjectCard({
  project,
  memberMap,
}: {
  project: Project;
  memberMap: Record<string, Member>;
}) {
  const assignments = project.assignments ?? [];
  const skills = project.required_skills ?? [];
  const statusLabel = STATUS_LABEL[project.status ?? ""] ?? project.status ?? "不明";
  const statusColor = STATUS_COLOR[project.status ?? ""] ?? "bg-muted text-muted-foreground";
  const remaining = daysLeft(project.period?.end);

  return (
    <div className="flex flex-col gap-3 rounded-xl border bg-card p-4 shadow-sm">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <p className="font-semibold leading-snug">{project.name}</p>
        <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${statusColor}`}>
          {statusLabel}
        </span>
      </div>

      {/* Period */}
      {project.period && (
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <CalendarRange className="h-3.5 w-3.5 shrink-0" />
          <span>
            {formatDate(project.period.start)} → {formatDate(project.period.end)}
          </span>
          {remaining != null && project.status === "active" && (
            <span
              className={`ml-auto rounded px-1.5 py-0.5 font-medium ${
                remaining < 0
                  ? "bg-destructive/10 text-destructive"
                  : remaining <= 14
                  ? "bg-orange-100 text-orange-700"
                  : "bg-muted text-muted-foreground"
              }`}
            >
              {remaining < 0 ? `${Math.abs(remaining)}日超過` : `残 ${remaining}日`}
            </span>
          )}
        </div>
      )}

      {/* Assigned members */}
      {assignments.length > 0 && (
        <div className="space-y-1">
          <p className="flex items-center gap-1 text-[11px] font-medium text-muted-foreground">
            <Users className="h-3.5 w-3.5" />
            アサイン中 ({assignments.length} 名)
          </p>
          <div className="flex flex-wrap gap-1.5">
            {assignments.map((a) => {
              const m = memberMap[a.member_id];
              return (
                <span
                  key={a.member_id}
                  className="flex items-center gap-1 rounded-md bg-secondary px-2 py-0.5 text-[11px]"
                  title={a.role ?? undefined}
                >
                  <span className="font-medium">{m?.name ?? a.member_id}</span>
                  {a.role && (
                    <span className="text-muted-foreground">· {a.role}</span>
                  )}
                </span>
              );
            })}
          </div>
        </div>
      )}

      {assignments.length === 0 && (
        <p className="text-[11px] text-muted-foreground">アサイン未設定</p>
      )}

      {/* Required skills */}
      {skills.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {skills.map((s) => (
            <span
              key={s}
              className="rounded-md border px-2 py-0.5 text-[10px] text-muted-foreground"
            >
              {s}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
