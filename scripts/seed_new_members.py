"""新規 AI エンジニア 4名を Notion ハブメンバーDB + Slack tweetチャンネルに追加.

追加メンバー:
  木村 大介  (NLP/LLM)
  原田 京子  (強化学習)
  長谷川 拓  (音声AI/マルチモーダル)
  岡田 あかり (ML基盤/MLflow)

Notionのどの PJ にも参加させない。

実行:
  uv run python scripts/seed_new_members.py
"""

import os
import sys
import time
import pathlib

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from notion_client import Client
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# ============================================================
# Notion ID
# ============================================================
HUB_MBR_DB_ID = "367c7942-de09-80e2-b2c9-c70f94d2aa72"

# ============================================================
# 新規メンバー定義
# ============================================================
NEW_MEMBERS = [
    {
        "名前":       "木村 大介",
        "email":      "kimura@abc.com",
        "役職":       "AIエンジニア",
        "スキル":     "Python, LLM fine-tuning, RAG, Transformers, Azure OpenAI, NLP",
        "経験年数":   4,
        "月次コスト": 680000,
        "一言メモ":   "NLP・LLM専門。社内のLLM活用基盤を整備中。",
    },
    {
        "名前":       "原田 京子",
        "email":      "harada@abc.com",
        "役職":       "AIエンジニア",
        "スキル":     "Python, PyTorch, 強化学習, シミュレーション, Azure ML, 最適化アルゴリズム",
        "経験年数":   3,
        "月次コスト": 630000,
        "一言メモ":   "強化学習と最適化が専門。ロボティクス・物流系AI経験あり。",
    },
    {
        "名前":       "長谷川 拓",
        "email":      "hasegawa@abc.com",
        "役職":       "AIエンジニア",
        "スキル":     "Python, PyTorch, 音声認識, Whisper, TTS, マルチモーダルLLM, Speech API",
        "経験年数":   5,
        "月次コスト": 730000,
        "一言メモ":   "音声AI・マルチモーダル専門。プロダクト組み込み実績多数。",
    },
    {
        "名前":       "岡田 あかり",
        "email":      "okada@abc.com",
        "役職":       "AIエンジニア",
        "スキル":     "Python, MLflow, Kubeflow, 特徴量エンジニアリング, AutoML, Azure ML, scikit-learn",
        "経験年数":   4,
        "月次コスト": 660000,
        "一言メモ":   "ML基盤・特徴量パイプライン設計が得意。実験管理の標準化を推進。",
    },
]

# ============================================================
# Slack tweetメッセージ定義
# ============================================================
SLACK_CHANNELS = ["tweet_kimura", "tweet_harada", "tweet_hasegawa", "tweet_okada"]

MESSAGES: dict[str, list[dict]] = {
    # ----------------------------------------------------------
    # tweet_kimura — 木村 大介（NLP/LLM）
    # ----------------------------------------------------------
    "tweet_kimura": [
        {"speaker": "木村 大介", "emoji": ":books:",
         "text": "社内の複数チームが使う共通RAGパイプラインを設計中。"
                 "Azure AI Searchとtext-embedding-3-largeの組み合わせで"
                 "Recall@5が0.71→0.89に改善。チャンクサイズとオーバーラップ設定が想像以上に効く。"},
        {"speaker": "木村 大介", "emoji": ":books:",
         "text": "LLM fine-tuningの実験記録。LoRAをQwenに適用してタスク固有データで追加学習。"
                 "フルファインチューニングの1/10のコストで精度が95%まで追いついた。"
                 "小さいモデルを賢くする方向が今後の主戦場になると思う。"},
        {"speaker": "木村 大介", "emoji": ":books:",
         "text": "Semantic Kernelのプラグイン設計を整理した。"
                 "前田さんのアーキテクチャを参考にしながら、関数オーケストレーションの"
                 "エラー伝播をどう扱うか悩んだ。最終的にフォールバック戦略をプラグイン内に持たせる設計に落とした。"},
        {"speaker": "木村 大介", "emoji": ":books:",
         "text": "プロンプトエンジニアリングとファインチューニングのどちらを使うか、"
                 "判断基準を言語化してみた。タスク固有データが1000件以上あればfine-tuning優位。"
                 "それ以下はRAG＋few-shotで戦える場合がほとんど。"},
        {"speaker": "木村 大介", "emoji": ":books:",
         "text": "NLPの仕事をしていて一番難しいのは評価指標の設計だと思う。"
                 "BLEUやROUGEは人間の評価と乖離することが多い。"
                 "最近はLLMをジャッジに使うG-Evalアプローチを試していてかなり有望。"},
    ],
    # ----------------------------------------------------------
    # tweet_harada — 原田 京子（強化学習）
    # ----------------------------------------------------------
    "tweet_harada": [
        {"speaker": "原田 京子", "emoji": ":robot_face:",
         "text": "強化学習の環境設計で詰まっていた問題、ようやく解決。"
                 "報酬関数のスケーリングが収束速度に直結することを再確認した。"
                 "Gymnasium + PyTorchの組み合わせで実験サイクルを回しやすくなった。"},
        {"speaker": "原田 京子", "emoji": ":robot_face:",
         "text": "物流最適化のシミュレーターを構築中。"
                 "実際の倉庫レイアウトをグラフ構造にして、"
                 "ピッキングルートをPPOで最適化する。収束まで3時間かかるのが悩み。"},
        {"speaker": "原田 京子", "emoji": ":robot_face:",
         "text": "Model-based RLとModel-free RLの使い分けを整理した。"
                 "サンプル効率を重視するなら前者、環境の複雑さに対応するなら後者。"
                 "実務では両方のハイブリッドが有効なことも多い。"},
        {"speaker": "原田 京子", "emoji": ":robot_face:",
         "text": "Azure MLでRLの分散学習を試した。"
                 "Ray RLlibをAzure MLの計算クラスターに載せる構成。"
                 "環境並列化でサンプル収集速度が8倍になった。"},
        {"speaker": "原田 京子", "emoji": ":robot_face:",
         "text": "強化学習エンジニアとして常に意識しているのは「報酬ハッキング」のリスク。"
                 "報酬関数の設計ミスがエージェントを意図しない方向に進化させる。"
                 "シミュレーションと実環境のギャップも含め、慎重に設計することが大事。"},
    ],
    # ----------------------------------------------------------
    # tweet_hasegawa — 長谷川 拓（音声AI）
    # ----------------------------------------------------------
    "tweet_hasegawa": [
        {"speaker": "長谷川 拓", "emoji": ":microphone:",
         "text": "Whisper large-v3の推論速度改善に取り組んだ。"
                 "CTranslate2でモデルを量子化してGPU推論。"
                 "精度をほぼ維持しつつ速度が3.2倍に。リアルタイム文字起こしに使えるレベルになった。"},
        {"speaker": "長谷川 拓", "emoji": ":microphone:",
         "text": "マルチモーダルLLMを使った会議支援システムを試作中。"
                 "音声→テキスト→要約→アクションアイテム抽出をパイプライン化。"
                 "GPT-4oのオーディオ入力対応が出てから一気に精度が上がった。"},
        {"speaker": "長谷川 拓", "emoji": ":microphone:",
         "text": "Text-to-Speechの品質評価が難しい。MOS（Mean Opinion Score）を"
                 "人手でやると時間がかかるので、UTMOSという自動評価指標を試している。"
                 "人間の評価との相関は0.85程度で実用的。"},
        {"speaker": "長谷川 拓", "emoji": ":microphone:",
         "text": "音声AIをプロダクトに組み込む際の一番の課題はレイテンシ。"
                 "エンドユーザーが「遅い」と感じる閾値は300ms程度。"
                 "ストリーミング推論と適切なバッファリングで200ms以内を実現できた。"},
        {"speaker": "長谷川 拓", "emoji": ":microphone:",
         "text": "音声認識と画像認識は技術的に似ている部分が多い。"
                 "どちらも時系列or空間のパターン認識で、Transformerが強い。"
                 "中村さんの画像AIの話を聞いていて、ViTとWhisperのアーキテクチャの"
                 "類似性を感じた。モダリティが違うだけで本質は同じ。"},
    ],
    # ----------------------------------------------------------
    # tweet_okada — 岡田 あかり（ML基盤）
    # ----------------------------------------------------------
    "tweet_okada": [
        {"speaker": "岡田 あかり", "emoji": ":gear:",
         "text": "MLflowでの実験管理を全チーム共通化できた。"
                 "モデルレジストリ＋自動タグ付けで、3ヶ月前の実験でも"
                 "再現できるようになった。「あの実験どうやったっけ」問題がなくなる。"},
        {"speaker": "岡田 あかり", "emoji": ":gear:",
         "text": "特徴量ストアの設計で学んだこと：オンライン特徴量（低レイテンシ）と"
                 "オフライン特徴量（バッチ処理）を分離することが鉄則。"
                 "Azure Cache for Redisをオンライン側に使う構成が安定している。"},
        {"speaker": "岡田 あかり", "emoji": ":gear:",
         "text": "AutoMLの使い所を整理した。ベースライン確認とハイパーパラメータ探索には有効。"
                 "ただし特徴量エンジニアリングはドメイン知識が必要で自動化が難しい。"
                 "AutoMLを出発点にして人間が改善するハイブリッドが現実解。"},
        {"speaker": "岡田 あかり", "emoji": ":gear:",
         "text": "Kubeflowのパイプライン依存関係の可視化機能が便利。"
                 "どのコンポーネントがボトルネックか一目で分かる。"
                 "山田さんのAzure ML Pipelineと設計思想が似ていて参考にしている。"},
        {"speaker": "岡田 あかり", "emoji": ":gear:",
         "text": "ML基盤エンジニアの価値は「モデルを作ること」ではなく"
                 "「モデルを作りやすい環境を作ること」だと思う。"
                 "地味に見えるが、基盤が整うとチーム全体の実験サイクルが劇的に速くなる。"
                 "縁の下の力持ちでいい。"},
    ],
}


# ============================================================
# ユーティリティ
# ============================================================

def section(title: str) -> None:
    print(f"\n{'=' * 55}\n{title}\n{'=' * 55}")


def t(content: str) -> list:
    return [{"text": {"content": content}}] if content else []


def load_env() -> None:
    env_path = pathlib.Path(__file__).resolve().parent.parent / ".env"
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# ============================================================
# STEP 1: Notion ハブメンバーDB に追加
# ============================================================

def add_members_to_notion(notion: Client) -> None:
    section("STEP 1: Notion ハブメンバーDB に新規 4名追加")
    for m in NEW_MEMBERS:
        notion.pages.create(
            parent={"database_id": HUB_MBR_DB_ID},
            properties={
                "名前":       {"title": t(m["名前"])},
                "email":      {"rich_text": t(m["email"])},
                "役職":       {"select": {"name": m["役職"]}},
                "スキル":     {"rich_text": t(m["スキル"])},
                "経験年数":   {"number": m["経験年数"]},
                "月次コスト": {"number": m["月次コスト"]},
                "一言メモ":   {"rich_text": t(m["一言メモ"])},
            },
        )
        print(f"  OK: {m['名前']} ({m['役職']}, {m['経験年数']}年)")
        time.sleep(0.3)


# ============================================================
# STEP 2: Slack チャンネル作成 + メッセージ投入
# ============================================================

def create_or_get_channel(slack: WebClient, name: str) -> str | None:
    try:
        resp = slack.conversations_create(name=name, is_private=False)
        ch_id = resp["channel"]["id"]
        print(f"  作成済み: #{name} ({ch_id})")
        return ch_id
    except SlackApiError as e:
        err = e.response.get("error", "")
        if err == "name_taken":
            r = slack.conversations_list(types="public_channel", limit=200)
            for ch in r["channels"]:
                if ch["name"] == name:
                    print(f"  既存チャンネル: #{name} ({ch['id']})")
                    return ch["id"]
            print(f"  WARN: #{name} 既存だが ID 取得失敗")
            return None
        elif err == "missing_scope":
            print(f"  ERROR: channels:manage スコープがありません")
            return None
        else:
            print(f"  ERROR: #{name} → {err}")
            return None


def post_messages(slack: WebClient, channel_id: str, messages: list[dict]) -> None:
    for m in messages:
        try:
            slack.chat_postMessage(
                channel=channel_id,
                text=m["text"],
                username=m["speaker"],
                icon_emoji=m["emoji"],
            )
        except SlackApiError as e:
            err = e.response.get("error", "")
            if err == "missing_scope":
                slack.chat_postMessage(channel=channel_id,
                                       text=f"[{m['speaker']}] {m['text']}")
            elif err in ("not_in_channel", "channel_not_found"):
                slack.conversations_join(channel=channel_id)
                slack.chat_postMessage(channel=channel_id, text=m["text"],
                                       username=m["speaker"], icon_emoji=m["emoji"])
            else:
                print(f"    ERROR: {err}")
                continue
        print(f"    OK [{m['speaker']}] {m['text'][:50]}...")
        time.sleep(0.4)


def add_slack_channels(slack: WebClient) -> None:
    section("STEP 2: Slack tweetチャンネル作成 + メッセージ投入")
    for ch_name in SLACK_CHANNELS:
        ch_id = create_or_get_channel(slack, ch_name)
        if not ch_id:
            continue
        msgs = MESSAGES.get(ch_name, [])
        print(f"  #{ch_name} に {len(msgs)} 件投入中...")
        post_messages(slack, ch_id, msgs)


# ============================================================
# main
# ============================================================

def main() -> int:
    load_dotenv()

    notion_token = os.getenv("NOTION_API_KEY")
    slack_token = os.getenv("SLACK_BOT_OAUTH_TOKEN")

    if not notion_token:
        print("ERROR: NOTION_API_KEY が .env に見つかりません")
        return 1
    if not slack_token:
        print("ERROR: SLACK_BOT_OAUTH_TOKEN が .env に見つかりません")
        return 1

    notion = Client(auth=notion_token)
    slack = WebClient(token=slack_token)

    add_members_to_notion(notion)
    add_slack_channels(slack)

    section("完了")
    print("  Notion ハブメンバーDB: 木村・原田・長谷川・岡田 を追加（計10名）")
    print("  Slack: tweet_kimura / tweet_harada / tweet_hasegawa / tweet_okada 作成・投入")
    print("  ※ どの PJ にもアサインしていません")
    return 0


if __name__ == "__main__":
    sys.exit(main())
