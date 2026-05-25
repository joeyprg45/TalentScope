"use client";

import { useEffect, useState } from "react";
import { BarChart2, Briefcase, DollarSign, User } from "lucide-react";
import { api } from "@/lib/api";
import type { Member } from "@/lib/types";
import { useChatContext } from "@/context/ChatContext";
import { Button } from "@/components/ui/button";

export default function MembersPage() {
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { openChat, sendMessage } = useChatContext();

  useEffect(() => {
    api.members()
      .then(setMembers)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  const handleSkillAnalysis = (member: Member) => {
    openChat();
    sendMessage(`${member.name} のスキル分析をして`);
  };

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

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">メンバー</h1>
        <p className="mt-1 text-sm text-muted-foreground">{members.length} 名登録</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {members.map((m) => (
          <MemberCard key={m.member_id} member={m} onAnalyze={handleSkillAnalysis} />
        ))}
      </div>
    </div>
  );
}

function MemberCard({
  member,
  onAnalyze,
}: {
  member: Member;
  onAnalyze: (m: Member) => void;
}) {
  return (
    <div className="flex flex-col gap-3 rounded-xl border bg-card p-4 shadow-sm">
      {/* Header */}
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
          <User className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate font-semibold">{member.name}</p>
          <p className="truncate text-xs text-muted-foreground">{member.role ?? "役職未設定"}</p>
        </div>
      </div>

      {/* Stats row */}
      <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
        {member.years_experience != null && (
          <span className="flex items-center gap-1">
            <Briefcase className="h-3.5 w-3.5" />
            {member.years_experience} 年
          </span>
        )}
        {member.monthly_cost != null && (
          <span className="flex items-center gap-1">
            <DollarSign className="h-3.5 w-3.5" />
            ¥{member.monthly_cost.toLocaleString()}
            <span className="text-[10px]">/月</span>
          </span>
        )}
      </div>

      {/* Skills */}
      {member.skills && member.skills.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {member.skills.map((s) => (
            <span
              key={s}
              className="rounded-md bg-secondary px-2 py-0.5 text-[11px] font-medium text-secondary-foreground"
            >
              {s}
            </span>
          ))}
        </div>
      )}

      {/* Action */}
      <Button
        size="sm"
        variant="outline"
        className="mt-auto w-full gap-1.5"
        onClick={() => onAnalyze(member)}
      >
        <BarChart2 className="h-3.5 w-3.5" />
        スキル分析
      </Button>
    </div>
  );
}
