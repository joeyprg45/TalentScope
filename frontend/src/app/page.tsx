"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Users, Briefcase, CheckCircle2 } from "lucide-react";

import { api } from "@/lib/api";
import type { Member, Project } from "@/lib/types";
import { HomeMemberTimeline } from "@/components/calendar/HomeMemberTimeline";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

// ── KPI card ──────────────────────────────────────────────────────────────────

type KpiCardProps = {
  label: string;
  value: number;
  unit: string;
  icon: React.ReactNode;
  highlight?: boolean;
};

function KpiCard({ label, value, unit, icon, highlight }: KpiCardProps) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 pt-5">
        <div
          className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${highlight ? "bg-amber-100 text-amber-600 dark:bg-amber-900/30 dark:text-amber-400" : "bg-muted text-muted-foreground"}`}
        >
          {icon}
        </div>
        <div>
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className="text-2xl font-bold leading-tight">
            {value}
            <span className="ml-0.5 text-sm font-normal text-muted-foreground">
              {unit}
            </span>
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Active project row ────────────────────────────────────────────────────────

function statusLabel(status: string | null | undefined): string {
  switch (status) {
    case "active":   return "進行中";
    case "planning": return "計画中";
    case "completed": return "完了";
    default:         return status ?? "不明";
  }
}

function statusVariant(status: string | null | undefined): "default" | "secondary" | "outline" {
  if (status === "active")   return "default";
  if (status === "planning") return "secondary";
  return "outline";
}

type ActiveProjectRowProps = {
  project: Project;
  members: Member[];
};

function ActiveProjectRow({ project, members }: ActiveProjectRowProps) {
  const teamMembers = (project.assignments ?? [])
    .map((a) => members.find((m) => m.member_id === a.member_id))
    .filter(Boolean) as Member[];

  return (
    <div className="rounded-lg border bg-muted/30 px-3 py-2.5">
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-medium leading-tight">{project.name}</span>
        <Badge variant={statusVariant(project.status)} className="shrink-0 text-[10px]">
          {statusLabel(project.status)}
        </Badge>
      </div>
      {project.period && (
        <p className="mt-0.5 text-[11px] text-muted-foreground">
          {project.period.start} 〜 {project.period.end}
        </p>
      )}
      {teamMembers.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {teamMembers.map((m) => (
            <span
              key={m.member_id}
              className="rounded-full bg-background px-2 py-0.5 text-[10px] text-muted-foreground ring-1 ring-border"
            >
              {m.name}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Unassigned member row ─────────────────────────────────────────────────────

type UnassignedRowProps = {
  member: Member;
};

function UnassignedRow({ member }: UnassignedRowProps) {
  return (
    <div className="rounded-lg border bg-muted/30 px-3 py-2">
      <p className="truncate text-sm font-medium">{member.name}</p>
      {member.role && (
        <p className="truncate text-[11px] text-muted-foreground">{member.role}</p>
      )}
      {member.skills && member.skills.length > 0 && (
        <div className="mt-1 flex flex-wrap gap-1">
          {member.skills.slice(0, 3).map((s) => (
            <span
              key={s}
              className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground"
            >
              {s}
            </span>
          ))}
          {member.skills.length > 3 && (
            <span className="text-[10px] text-muted-foreground">
              +{member.skills.length - 3}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function HomePage() {
  const { data: members = [] } = useQuery({
    queryKey: ["members"],
    queryFn: api.members,
  });
  const { data: projects = [] } = useQuery({
    queryKey: ["projects"],
    queryFn: api.projects,
  });
  const activeProjects = useMemo(
    () => projects.filter((p) => p.status === "active" || p.status === "planning"),
    [projects],
  );
  const completedProjects = useMemo(
    () => projects.filter((p) => p.status === "completed"),
    [projects],
  );
  const assignedIds = useMemo(
    () =>
      new Set(
        activeProjects.flatMap((p) => p.assignments?.map((a) => a.member_id) ?? []),
      ),
    [activeProjects],
  );
  const unassignedMembers = useMemo(
    () => members.filter((m) => !assignedIds.has(m.member_id)),
    [members, assignedIds],
  );

  return (
    <div className="h-full overflow-y-auto space-y-6 p-6">
      {/* B: KPI */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <KpiCard
          label="メンバー数"
          value={members.length}
          unit="人"
          icon={<Users className="h-5 w-5" />}
        />
        <KpiCard
          label="進行中 PJ"
          value={activeProjects.length}
          unit="件"
          icon={<Briefcase className="h-5 w-5" />}
        />
        <KpiCard
          label="未アサイン"
          value={unassignedMembers.length}
          unit="人"
          icon={<Users className="h-5 w-5" />}
          highlight={unassignedMembers.length > 0}
        />
        <KpiCard
          label="完了 PJ"
          value={completedProjects.length}
          unit="件"
          icon={<CheckCircle2 className="h-5 w-5" />}
        />
      </div>

      {/* A: タイムライン */}
      <HomeMemberTimeline members={members} projects={projects} />

      {/* C + D */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {/* C: アクティブPJ */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">進行中プロジェクト</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {activeProjects.map((p) => (
              <ActiveProjectRow key={p.project_id} project={p} members={members} />
            ))}
            {activeProjects.length === 0 && (
              <p className="text-xs text-muted-foreground">なし</p>
            )}
          </CardContent>
        </Card>

        {/* D: 未アサイン */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">未アサインメンバー</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {unassignedMembers.map((m) => (
              <UnassignedRow key={m.member_id} member={m} />
            ))}
            {unassignedMembers.length === 0 && (
              <p className="text-xs text-muted-foreground">全員アサイン済み</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
