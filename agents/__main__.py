"""TalentScope Agent CLI テストエントリポイント.

使い方:
  uv run python -m agents                                             # インタラクティブチャット
  uv run python -m agents --mode skill --target kobayashi@abc.com
  uv run python -m agents --mode assignment --target <project_id>
  uv run python -m agents --mode assignment --target <project_id> --axis cost
"""
from __future__ import annotations

import argparse
import asyncio
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


from agents.config import AgentSettings
from agents.orchestrator import AgentMode, TalentScopeOrchestrator
from semantic_kernel.contents.chat_history import ChatHistory


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TalentScope Agent CLI")
    parser.add_argument(
        "--mode",
        choices=["chat", "skill", "assignment"],
        default="chat",
        help="実行モード (default: chat)",
    )
    parser.add_argument(
        "--target",
        default="",
        help="skill: member_id(email) / assignment: project_id",
    )
    parser.add_argument(
        "--axis",
        choices=["ability", "cost"],
        default="ability",
        help="アサイン提案の軸 (default: ability)",
    )
    return parser.parse_args()


async def _run_chat(orchestrator: TalentScopeOrchestrator) -> None:
    """インタラクティブチャットループ."""
    history = ChatHistory()
    print("TalentScope Agent — チャットモード（終了: quit）\n")
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if user_input.lower() in ("quit", "exit", "q"):
            break
        if not user_input:
            continue
        print("Agent: ", end="", flush=True)
        async for chunk in orchestrator.chat(user_input, AgentMode.BASE_CHAT, history):
            print(chunk, end="", flush=True)
        print("\n")


async def _run_report(
    orchestrator: TalentScopeOrchestrator,
    mode: str,
    target: str,
    axis: str,
) -> None:
    """レポートを生成してMarkdownをstdoutに出力する."""
    if not target:
        print("エラー: --target は skill/assignment モードで必須です", file=sys.stderr)
        sys.exit(1)

    agent_mode = AgentMode.SKILL_ANALYSIS if mode == "skill" else AgentMode.ASSIGNMENT
    label = "個人スキル分析" if mode == "skill" else f"アサイン提案（{axis}）"
    print(f"[{label}] target={target} でレポートを生成中...\n", file=sys.stderr)

    summary, report_md = await orchestrator.generate_report(
        mode=agent_mode,
        target_id=target,
        axis=axis,
    )

    print("=" * 60)
    print("■ サマリー（チャット表示用）")
    print("=" * 60)
    print(summary)
    print()
    print("=" * 60)
    print("■ フルレポート（Markdown）")
    print("=" * 60)
    print(report_md)


async def main() -> None:
    args = _parse_args()
    try:
        settings = AgentSettings.from_env()
    except EnvironmentError as exc:
        print(f"設定エラー: {exc}", file=sys.stderr)
        sys.exit(1)

    orchestrator = TalentScopeOrchestrator(settings)

    if args.mode == "chat":
        await _run_chat(orchestrator)
    else:
        await _run_report(orchestrator, args.mode, args.target, args.axis)


if __name__ == "__main__":
    asyncio.run(main())
