"""Slack 書き込みテスト: 個人チャンネル + プロジェクトチャンネル作成."""
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

load_dotenv()
client = WebClient(token=os.getenv("SLACK_BOT_OAUTH_TOKEN"))


def post(channel_id: str, speaker: str, emoji: str, text: str) -> None:
    try:
        client.chat_postMessage(
            channel=channel_id, text=text, username=speaker, icon_emoji=emoji
        )
        preview = text[:50] + "..." if len(text) > 50 else text
        print(f"  OK [{speaker}] {preview}")
    except SlackApiError as e:
        err = e.response.get("error", "unknown")
        print(f"  NG [{speaker}] {err}")
    time.sleep(0.5)


TWEETS = {
    "C0B51HALTNV": [  # tweet_kobayashi
        ("小林 拓海", ":hammer_and_wrench:", "Azure Cosmos DB のパーティションキー設計、今日やっと腑に落ちた。クロスパーティションクエリを避けるには「一番多いアクセスパターン」に合わせてキーを選ぶのが正解。最初に全部設計するの大事だなと痛感。"),
        ("小林 拓海", ":hammer_and_wrench:", "「Designing Data-Intensive Applications」読み直してる。分散システムの一貫性モデルの章、去年読んだときより全然理解できる。実際にCosmosDB触った経験があるからだと思う。やっぱり手を動かした後に読む本は全然違う。"),
        ("小林 拓海", ":hammer_and_wrench:", "FastAPIのDependency Injectionの仕組み、ようやく使いこなせてきた。DBクライアントをDI経由で渡すようにしたらテストが劇的に書きやすくなった。フレームワークの設計に従うって大事。"),
    ],
    "C0B4TB12T7D": [  # tweet_maeda
        ("前田 彩", ":brain:", "Attention Is All You Needを改めて読んだ。Self-Attentionの計算量がO(n^2)になる理由、図と一緒に見るとすごくわかりやすい。LLMの文脈長が問題になる理由が根本から理解できた気がする。"),
        ("前田 彩", ":brain:", "RAGとFine-tuningの使い分けについて考えてた。知識の更新頻度が高いドメインはRAG一択だと思う。Fine-tuningはモデルの「振る舞い」を変えるのに向いてて、「知識」を入れるのには向いてない。この区別を最初から理解してたかった。"),
        ("前田 彩", ":brain:", "Semantic Kernelのプラグイン設計、抽象化レイヤーがきれいだなと思う一方で、デバッグがしんどい。どのプラグインがどの順番で呼ばれたか追いにくい。ログを充実させるのが結局一番の解決策な気がしてる。"),
    ],
    "C0B4JGP19NX": [  # tweet_sato
        ("佐藤 健太", ":computer:", "ReactのuseCallbackとuseMemoの使い分け、やっと整理できた。「関数を安定させたい→useCallback」「計算結果をキャッシュしたい→useMemo」この一言で覚える。最適化は計測してから、が鉄則らしい。"),
        ("佐藤 健太", ":computer:", "TypeScriptのジェネリクス、難しいと思ってたけど「型の変数」と考えたら一気にわかった。前田さんに「Tは型のプレースホルダーと思えばいい」って言われてスッキリ。聞いてよかった。"),
        ("佐藤 健太", ":computer:", "Next.jsのApp RouterとPages Routerの違い、チュートリアルやってみた。Server Componentsの概念が面白い。サーバーで描画してクライアントに送るのに、Reactのコンポーネントの書き方でできるの不思議。"),
    ],
}

PROJ_MSGS = [
    ("田中 誠",   ":briefcase:", "今スプリントの方針です。優先度：①Cosmos DBスキーマ確定 ②Ingest層の基本実装 ③エージェントのプロトタイプ。完成度より「動く最小構成」を優先してください。詰まったら抱え込まず、その日中にスレッドに書いてください。"),
    ("小林 拓海", ":hammer_and_wrench:", "CosmosDBのスキーマ設計完了しました。members / projects / meetings の3コンテナ構成で、partitionKeyは各コンテナの主キーで統一します。今日中にCRUD動作確認して共有します。"),
    ("前田 彩",   ":brain:", "Semantic Kernelのプラグイン設計について相談です。Notion取り込みプラグインとCosmosDB検索プラグインを分けて実装中ですが、エージェントが自動判断できるか確認したい。明日のMTGで話しましょう。"),
    ("山田 花奈", ":gear:", "CI/CDパイプラインの設定が完了しました。GitHub ActionsでPRマージ→自動ビルド→Azure Container Appsへデプロイの流れを構築。ローカルはdocker compose upで統一。README更新したので確認よろしくです。"),
    ("佐藤 健太", ":computer:", "チャットUIのローカル環境、起動確認できました。localhost:3000でアクセスできます。エラー表示とローディング状態の実装が終わったので、APIの繋ぎ込みテストをしてもらえると助かります。"),
    ("前田 彩",   ":brain:", "エージェントのプロトタイプ動きました！「小林さんのスキルを教えて」という質問に対してCosmosDBからデータを取得して自然な文章で回答できています。精度はまだ粗いですが基本フローは完成です。"),
]


def main() -> None:
    print("=== 個人チャンネルへ投稿 ===")
    for ch_id, msgs in TWEETS.items():
        for speaker, emoji, text in msgs:
            post(ch_id, speaker, emoji, text)

    print("\n=== proj-llm-agent-infra チャンネル作成 ===")
    proj_ch_id = None
    try:
        resp = client.conversations_create(name="proj-llm-agent-infra", is_private=False)
        proj_ch_id = resp["channel"]["id"]
        print(f"  作成済み: {proj_ch_id}")
    except SlackApiError as e:
        err = e.response.get("error", "")
        if err == "name_taken":
            cursor = None
            while True:
                r = client.conversations_list(types="public_channel", limit=200, **({"cursor": cursor} if cursor else {}))
                for ch in r["channels"]:
                    if ch["name"] == "proj-llm-agent-infra":
                        proj_ch_id = ch["id"]
                        print(f"  既存チャンネル: {proj_ch_id}")
                        break
                if proj_ch_id:
                    break
                cursor = r.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break
        else:
            print(f"  NG: {err}")

    if proj_ch_id:
        try:
            client.conversations_join(channel=proj_ch_id)
        except SlackApiError:
            pass
        print("\n=== proj-llm-agent-infra へ投稿 ===")
        for speaker, emoji, text in PROJ_MSGS:
            post(proj_ch_id, speaker, emoji, text)

    print("\n=== 完了 ===")


if __name__ == "__main__":
    main()
