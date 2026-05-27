"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import type { ClarificationPrompt } from "@/lib/types";

type Props = {
  prompt: ClarificationPrompt;
  onSubmit: (answerId: string, answerText?: string) => void;
};

export function ClarificationPanel({ prompt, onSubmit }: Props) {
  const [submitted, setSubmitted] = useState(false);
  const [freeText, setFreeText] = useState("");
  const hasOptions = prompt.options && prompt.options.length > 0;

  const handleOption = (id: string) => {
    if (submitted) return;
    setSubmitted(true);
    onSubmit(id, undefined);
  };

  const handleFreeText = () => {
    if (submitted) return;
    const v = freeText.trim();
    if (!v) return;
    setSubmitted(true);
    onSubmit("other", v);
  };

  return (
    <div className="border-t bg-indigo-50/60 px-3 py-2 dark:bg-indigo-950/30">
      <p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-indigo-700 dark:text-indigo-300">
        🤖 AI からの質問
      </p>
      <p className="mb-2 whitespace-pre-wrap text-xs text-foreground">{prompt.question}</p>

      {hasOptions && (
        <div className="mb-2 overflow-hidden rounded-lg border bg-background text-xs">
          {prompt.options.map((opt, i) => (
            <button
              key={opt.id}
              onClick={() => handleOption(opt.id)}
              disabled={submitted}
              className={cn(
                "flex w-full items-start gap-2 px-2.5 py-1.5 text-left transition-colors",
                !submitted && "hover:bg-primary/10 hover:text-primary",
                i > 0 && "border-t",
                submitted && "opacity-50",
              )}
            >
              <span className="font-semibold">{opt.label}</span>
              {opt.description && (
                <span className="leading-snug text-muted-foreground">{opt.description}</span>
              )}
            </button>
          ))}
        </div>
      )}

      <div className="flex items-center gap-1.5">
        <input
          type="text"
          value={freeText}
          onChange={(e) => setFreeText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleFreeText();
          }}
          placeholder={hasOptions ? "その他（自由記述）" : "回答を入力"}
          disabled={submitted}
          className="flex-1 rounded border bg-background px-2 py-1 text-xs outline-none placeholder:text-muted-foreground focus:ring-1 focus:ring-primary disabled:opacity-50"
        />
        <button
          onClick={handleFreeText}
          disabled={submitted || !freeText.trim()}
          className="rounded bg-primary px-2 py-1 text-xs text-primary-foreground hover:opacity-90 disabled:opacity-40"
        >
          送信
        </button>
      </div>
    </div>
  );
}
