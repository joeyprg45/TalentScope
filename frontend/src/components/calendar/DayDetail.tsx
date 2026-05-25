"use client";

import type { Project } from "@/lib/types";

type Props = {
  projects: Project[];
  date: string;
};

export function DayDetail({ projects, date }: Props) {
  const active = projects.filter(
    (p) => p.period && p.period.start <= date && date <= p.period.end,
  );

  const [y, m, d] = date.split("-");
  const label = `${y}年${parseInt(m)}月${parseInt(d)}日`;

  return (
    <div className="rounded-xl border bg-card p-4 shadow-sm">
      <h2 className="mb-3 text-sm font-semibold">
        {label} に稼働中のプロジェクト
        <span className="ml-2 text-xs font-normal text-muted-foreground">
          {active.length} 件
        </span>
      </h2>

      {active.length === 0 ? (
        <p className="text-xs text-muted-foreground">この日に稼働中のプロジェクトはありません。</p>
      ) : (
        <ul className="space-y-2">
          {active.map((p) => {
            const members = p.assignments?.filter(
              (a) => a.start && a.end && a.start <= date && date <= a.end,
            ) ?? [];
            return (
              <li key={p.project_id} className="rounded-lg border bg-background px-3 py-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-sm font-medium">{p.name}</span>
                  {p.status && (
                    <span className="shrink-0 rounded-full bg-secondary px-2 py-0.5 text-[10px] font-medium text-secondary-foreground">
                      {p.status}
                    </span>
                  )}
                </div>
                {members.length > 0 && (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {members.map((a) => (
                      <span
                        key={a.member_id}
                        className="text-[10px] text-muted-foreground"
                      >
                        {a.member_id}{a.role ? ` (${a.role})` : ""}
                      </span>
                    ))}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
