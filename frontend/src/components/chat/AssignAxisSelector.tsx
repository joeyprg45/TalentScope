"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

const AXES = [
  { id: "ability", name: "能力重視",     desc: "スキル・実績・MTGリーダーシップを最優先" },
  { id: "cost",    name: "コスト重視",   desc: "要件を満たす範囲でチームコストを最小化" },
  { id: "growth",  name: "育成重視",     desc: "ジュニアの成長機会を最大化" },
  { id: "synergy", name: "シナジー重視", desc: "過去の協働実績でチーム連携を最大化" },
] as const;

export type AssignAxis = (typeof AXES)[number]["id"];

type Props = {
  onChange: (axis: AssignAxis) => void;
  onCancel?: () => void;
};

export function AssignAxisSelector({ onChange, onCancel }: Props) {
  const [selected, setSelected] = useState(false);

  return (
    <div className="border-t px-3 py-2">
      <p className="mb-1.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        評価軸を選択してください
      </p>
      <div className="overflow-hidden rounded-lg border text-xs">
        {AXES.map((axis, i) => (
          <button
            key={axis.id}
            onClick={() => { if (selected) return; setSelected(true); onChange(axis.id); }}
            disabled={selected}
            className={cn(
              "flex w-full items-start gap-2 px-2.5 py-1.5 text-left transition-colors",
              !selected && "hover:bg-primary/10 hover:text-primary",
              i > 0 && "border-t",
            )}
          >
            <span className="w-[5.5rem] shrink-0 font-semibold">{axis.name}</span>
            <span className="leading-snug text-muted-foreground">{axis.desc}</span>
          </button>
        ))}
      </div>
      {onCancel && !selected && (
        <button
          onClick={onCancel}
          className="mt-1.5 w-full text-center text-[10px] text-muted-foreground hover:underline"
        >
          キャンセル（通常チャットとして送信）
        </button>
      )}
    </div>
  );
}
