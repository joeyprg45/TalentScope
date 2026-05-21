"""Slack プロジェクトチャンネル作成 + サンプル会話投入スクリプト.

DRY_RUN=True にすると投稿内容を表示するだけで実際には投稿しない。
"""

import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# ---- 設定 ----
DRY_RUN = False  # True: 表示のみ / False: 実際に投稿

EXISTING_CHANNELS: dict[str, str] = {
    "all-abctechnologies": "C0B4UBF7JTE",
    "tweet_kobayashi":     "C0B51HALTNV",
    "tweet_maeda":         "C0B4TB12T7D",
    "tweet_sato":          "C0B4JGP19NX",
}

PROJECT_CHANNEL_NAMES = [
    "proj-llm-agent-infra",
    "proj-interviewer-ai",
    "proj-finance-prediction",
]

# ---- ペルソナ設定 ----
PERSONA = {
    "小林 拓海": ":hammer_and_wrench:",
    "前田 彩":   ":brain:",
    "佐藤 健太": ":computer:",
    "田中 誠":   ":briefcase:",
    "山田 花奈": ":gear:",
}


def msg(speaker: str, text: str) -> dict:
    return {"speaker": speaker, "emoji": PERSONA[speaker], "text": text}


# ---- サンプルメッセージ ----
MESSAGES: dict[str, list[dict]] = {
    "all-abctechnologies": [
        msg("田中 誠",   "みなさん、今週のスプリント計画をお知らせします。LLMエージェント基盤チームはCosmosDB接続の安定化、面接AIチームはモデル選定フェーズに入ります。難しいタスクも多いですが、チーム全体で協力してやり切りましょう！何か困ったことがあれば遠慮なく相談してください💪"),
        msg("山田 花奈", "CI/CDパイプラインの改善完了しました🎉 今まで12分かかっていたビルドが4分30秒に短縮できました。GitHub Actionsのジョブ並列化とDockerレイヤーキャッシュの最適化が効いています。プルリクエスト出したので確認よろしくです。"),
        msg("小林 拓海", "CosmosDBの本番環境接続、完了しました！パーティションキーの設計で2日詰まってましたが、member_idをキーにすることで一気に解決しました。読み取りコストも想定の1/3に収まっています。田中さんのアドバイスが効きました、ありがとうございます。"),
        msg("前田 彩",   "RAGパイプラインの精度改善の報告です。text-embedding-3-small + コサイン類似度検索で、ベンチマーク質問に対するTopK精度が67% → 83%に改善しました。チャンクサイズを512→256に落としたのが大きかったです。次はリランキング導入を検討中です。"),
        msg("田中 誠",   "【リマインド】明日14:00から全社MTGです。各プロジェクトの進捗共有と次スプリントの計画確認を行います。スライドの準備は各チームリーダーお願いします。オンライン参加の方はMeetリンクを確認してください。"),
        msg("佐藤 健太", "チャットUIのデモ環境、起動確認できました！localhost:3000でアクセスできます。エラー表示とローディング状態の実装が終わったので、バックエンドチームはAPIの繋ぎ込みテストをしてもらえると助かります。"),
    ],
    "tweet_kobayashi": [
        msg("小林 拓海", "今日はCosmosDBのパーティションキー設計で3時間詰まった。最初はproject_idをキーにしようとしたけど、クロスパーティションクエリが激遅になって詰んだ。member_idに変えたら一発で解決。設計段階でちゃんと考えないといけなかった。反省。"),
        msg("小林 拓海", "FastAPIのエラーハンドリング、ようやく綺麗に書けるようになってきた。@app.exception_handler でHTTPExceptionとValueErrorを一括で拾うパターンが気持ちいい。エラーレスポンスの形式を統一できて、フロントの佐藤くんも喜んでくれた。"),
        msg("小林 拓海", "昨日23時まで実装してたやつ、今朝テストしたら全部通った😭 嬉しすぎる。CosmosDB のページネーション実装、continuation_token の扱いが地味に難しかった。ドキュメントが少ない部分だったので、SDKのソースコード読んで解決した。"),
        msg("小林 拓海", "Azureポータルがたまに意味わからん挙動をする。Cosmos DBのインデックスポリシー変更したはずなのに反映されてない→5分後に気づいたら反映されてた。非同期で適用されるの知らなかった。ドキュメントに書いてあったけど読んでなかった俺が悪い。"),
        msg("小林 拓海", "バックエンドエンジニア3年目、最近ようやくアーキテクチャを考えながら書けるようになってきた気がする。1年目は「動けばいい」、2年目は「綺麗に書きたい」、3年目は「設計から考えたい」という感じで意識が変わってきてる。田中さんみたいになりたい。"),
        msg("小林 拓海", "前田さんのRAGコードを読んだら勉強になりすぎた。埋め込みベクトルの生成からコサイン類似度検索まで、Pythonで100行くらいでできるんだな。AIは専門外だと思ってたけど、少し触れるようになりたくなってきた。"),
        msg("小林 拓海", "CosmosDB SDKのバッチ処理、地味に詰まりポイントがある。bulk_upsertで1リクエスト100件の制限があるのを知らなくて、500件投入しようとしてエラーになった。分割してリトライする処理を書いた。こういう細かいことは経験しないとわからない。"),
        msg("小林 拓海", "今日チームMTGで「小林さんのDB設計が安定してる」って田中さんに言ってもらえた。素直に嬉しかった。自分はスピードよりも安定性と堅牢性を重視してるので、それが伝わった気がして嬉しい。もっと頑張ろう。"),
    ],
    "tweet_maeda": [
        msg("前田 彩", "Semantic KernelのPluginアーキテクチャ、かなりよくできてる。AutoFunctionCallingで複数のプラグインをオーケストレーションできるの便利。ただ、プラグイン間の依存関係が複雑になるとデバッグが辛くなる予感がある。今のうちに設計を整理しておきたい。"),
        msg("前田 彩", "RAG vs Fine-tuning の選択、今のプロジェクトではRAGが正解だと思う。理由：①ドメイン知識の更新頻度が高い ②説明可能性が必要 ③データ量がFine-tuningには不十分。ただし2年後にデータが溜まったら再検討すべき。今の判断が正解かどうかは結果で証明するしかない。"),
        msg("前田 彩", "text-embedding-3-smallのベンチマーク結果が出た。largeモデルと比較して精度は92%程度だが、コストは1/5以下。今のユースケースでは十分なので3-smallで行く。コスパを意識しないとAzureの課金が怖いことになる。"),
        msg("前田 彩", "エンジニアとして5年やってきて、最近「何を作るか」より「なぜ作るか」を考えることが増えた。技術力は手段であって目的じゃない。TalentScopeも「面白いAIが作れる」じゃなくて「採用と配置のミスマッチを減らす」ために作ってる。この軸がブレると良いものは作れない。"),
        msg("前田 彩", "チャンクサイズを512→256に変えたらRAGの精度が16pt上がった。直感的には「大きいチャンクの方が文脈が保てる」と思ってたけど逆だった。Notionの1ブロック≒1意味単位が256トークン前後に収まることが多いから、256の方が意味境界と一致しやすいんだと思う。"),
        msg("前田 彩", "Semantic KernelのPlannerを試した。AutoPlannerはプロンプトが複雑になると計画がブレる。今のところHandlebars Plannerの方が制御しやすい。エージェントFWの選択は「何ができるか」じゃなくて「何がコントロールできるか」で選ぶべきだと思う。"),
        msg("前田 彩", "前田流エラーデバッグ術：①LLMの出力をそのままログに残す ②プロンプトを1行ずつ変えながらアブレーション ③「なぜそう答えたか」を逆算する。これやると大体どこが問題かわかる。デバッグはLLM相手でも人間相手でもやることは同じ。"),
        msg("前田 彩", "AIエンジニアのキャリア、正直「これが正解」って言える人は今の世界にいないと思う。技術の変化が速すぎて、2年後の正解が見えない。だから私は「なぜ動くかを理解する」ことに一番時間をかけてる。実装は変わっても原理は残るから。"),
    ],
    "tweet_sato": [
        msg("佐藤 健太", "useEffectのdependency arrayでまたやらかした。空配列にしたら無限ループになって、原因わかるまで30分かかった。Reactの挙動、まだちゃんと理解できてないな。前田さんに聞いたら5秒で解決してくれたけど、恥ずかしかった。"),
        msg("佐藤 健太", "TypeScriptの型定義、やっと楽しくなってきた。最初は「なんでJSに型つけるんだ」って思ってたけど、大きなコードベースで作業してると型があるだけで全然違う。コンパイルエラーが実行前に気づける、本当に助かる。"),
        msg("佐藤 健太", "田中さんに「フロントのコードが読みやすくなった」って言ってもらえた。3ヶ月前は「もう少しコンポーネント分割考えよう」ってよく言われてたから、成長実感できて嬉しかった。まだまだだけど少しずつ良くなってる。"),
        msg("佐藤 健太", "バックエンドのAPIに繋ぎ込んで、初めてEnd-to-Endで動いた！小林さんが作ったAPIのレスポンス形式が綺麗すぎて、フロント側ほぼ手を加えなくて良かった。バックエンドの人が良い仕事をすると、フロントも楽になるんだな。"),
        msg("佐藤 健太", "Next.jsのSSRとCSRの使い分けがまだふんわりしてる。パフォーマンスとSEOとユーザー体験のトレードオフがあるのはわかるんだけど、どう判断すればいいのか。田中さんか前田さんに相談してみよう。"),
        msg("佐藤 健太", "デザイナーがいないプロジェクトでUIを作るのが一番難しい。自分の「いい感じ」の感覚を信じていいのかわからない。Tailwind CSS使ってtailwindui.comのコンポーネント参考にしてるけど、もっとセンス磨きたい。"),
        msg("佐藤 健太", "2年目エンジニアとして感じること：「わからないこと」は減ってきたけど「わかっていないことの深さ」はむしろ増えてる気がする。表面的なAPIの使い方はわかるけど、なぜそう設計されてるかは全然わかってない。田中さんや前田さんはその「なぜ」から話せるのがすごい。"),
    ],
    "proj-llm-agent-infra": [
        msg("田中 誠",   "今スプリントの方針です。優先度：①Cosmos DBスキーマ確定 ②Ingest層の基本実装 ③エージェントのプロトタイプ。完成度より「動く最小構成」を優先してください。詰まったら抱え込まず、その日中にスレッドに書いてください。"),
        msg("小林 拓海", "CosmosDBのスキーマ案を作りました。コンテナ：members / projects / tasks の3本構成。partitionKeyは /member_id, /project_id, /project_id で統一する予定です。レビューお願いします。"),
        msg("田中 誠",   "小林さんのスキーマ確認しました。基本的にOKです。一点だけ：tasksコンテナのpartitionKeyですが、メンバーをまたいだタスク集計クエリが多い場合は /assignee の方がクロスパーティションを減らせます。どちらのクエリパターンが多いか確認してから決めましょう。"),
        msg("小林 拓海", "田中さんフィードバックありがとうございます。エージェントのユースケースを前田さんに確認したら「メンバーごとのタスク履歴を見ることが多い」とのことだったので、/member_id に変更しようと思います。"),
        msg("前田 彩",   "Semantic Kernelのプラグイン設計について相談です。現在、Notion取り込みプラグインとCosmosDB検索プラグインを分けて実装中なのですが、エージェントがどちらを呼ぶかを自動判断できるか心配です。明示的なプランナーを使うべきか、AutoFunctionCallingに任せるべきか迷ってます。"),
        msg("田中 誠",   "前田さん、まずAutoFunctionCallingで試してみて、判断がブレる場合にプランナーを入れる順番でいいと思います。ハンドルズプランナーは制御しやすい反面、プロンプト設計のコストが高いので、最初から入れるとオーバーエンジニアリングになりがちです。"),
        msg("山田 花奈", "デプロイ環境の提案です。Azure Container Apps + GitHub Actions のCI/CDを構成しました。PRマージで自動ビルド・デプロイが走ります。ローカル開発環境もDockerfileを整備したので、誰でも`docker compose up`で立ち上がります。README更新したのでご確認を。"),
        msg("佐藤 健太", "フロント側のAPI仕様を確認させてください。/api/members エンドポイントのレスポンスに、スキルタグのリストを含めてほしいのですが可能ですか？UIでスキルバッジを表示したくて。"),
        msg("小林 拓海", "佐藤さん、対応できます。現在のレスポンスに `skills: string[]` フィールドを追加します。Cosmos DBのmembersコンテナにはすでに `skills` が配列で入っているので、パースするだけです。明日中に対応します。"),
        msg("前田 彩",   "エージェントのプロトタイプ動きました🎉 「小林さんはどんなスキルを持っていますか？」という質問に対して、CosmosDBからデータを取得して自然な文章で回答できています。精度はまだ粗いですが、基本フローは完成です。"),
        msg("山田 花奈", "ビルド時間がまだ少し長い（8分）です。ベースイメージを python:3.12-slim に変えて、pip install の --no-cache-dir を使うように変更したら、もう2分くらい削れると思います。試してみます。"),
        msg("田中 誠",   "スプリントレビューの時間が取れました。明後日16:00、30分で各自の進捗を話してください。「できたこと」だけじゃなく「詰まったこと・気づいたこと」も共有してください。チーム全体の学びになるので。"),
    ],
    "proj-interviewer-ai": [
        msg("前田 彩",   "面接AIの設計方針を提案します。評価軸：①技術力（コーディング・設計） ②コミュニケーション ③カルチャーフィット の3軸で構造化面接を実施。各軸にルーブリックを持つLLMエージェントを配置する構成を想定しています。"),
        msg("田中 誠",   "前田さんの提案、方向性はいいと思います。一点確認：面接フローは「AI主導」「人間主導でAIがサポート」どちらを想定していますか？後者の方が実用性は高いですが、エージェントの自律度が落ちる。ハッカソンのデモとして映えるのは前者かもしれない。"),
        msg("前田 彩",   "田中さん、デモ観点では「AI主導の構造化面接」の方が映えますね。実用フェーズでは人間主導に切り替えるオプションを設けるとして、今は全自動フローを実装してデモインパクトを取りにいきます。"),
        msg("佐藤 健太", "フロント側の実装を担当しますが、面接フロー画面って一番難しいUIになりそう。リアルタイムでAIの質問が流れてきて、回答を入力して、評価結果が表示される。Websocketも使う可能性ありますか？"),
        msg("前田 彩",   "佐藤さん、まずはpollingで実装してみましょう。WebSocketはリアルタイム性が必要になったら追加で検討する形で。デモなので1秒ごとのpollingで十分だと思います。最初からWebSocketを入れると実装コストが高い。"),
        msg("佐藤 健太", "ありがとうございます、pollingで進めます。前田さんのアドバイスって毎回「最初はシンプルに、必要になったら複雑にする」なんですよね。自分はすぐ最善策を実装しようとして詰まるので、参考にしてます。"),
        msg("田中 誠",   "面接質問のテンプレート、私の方でレビューしました。技術系の質問が少し具体的すぎて、非エンジニアポジションの評価に使いにくいかもしれません。役職別にテンプレートを分けることを検討してください。"),
        msg("前田 彩",   "田中さんご指摘通りです。とりあえず今は「エンジニア向け」のテンプレートで動く形を作って、ポジション別展開はフェーズ2にします。スコープを絞らないとデモまでに間に合わない。"),
    ],
    "proj-finance-prediction": [
        msg("前田 彩",   "大手金融向け予測モデルの設計案です。時系列の融資データから焦げ付きリスクを予測するモデル。特徴量エンジニアリングが鍵になる予感。まずデータの前処理パイプラインから設計します。"),
        msg("山田 花奈", "MLOps観点のレビューです。モデルの学習パイプラインをAzure ML Pipelineで管理することを提案します。データバージョニング、実験管理、モデルレジストリまで一気通貫で管理できる。運用コストが大幅に下がります。"),
        msg("田中 誠",   "山田さんのMLOps提案、良いです。金融向けはモデルの説明可能性と監査ログが必須になるので、実験管理をしっかりやることは必然的な要件です。追加で、モデルの更新判断プロセスも設計しておきましょう。"),
        msg("前田 彩",   "LightGBMとニューラルネットワークの比較実験を回しています。金融データは欠損が多く、LightGBMの方が頑健な結果が出ています。説明可能性もSHAP値で担保できるので、今のところLightGBMが有力候補。"),
        msg("山田 花奈", "Azure ML のパイプラインでデータ前処理から学習まで自動化できました。毎朝0時に最新データで再学習 → 精度が閾値を超えれば自動デプロイするフローを構築中。手動オペレーションを極力排除したい。"),
        msg("田中 誠",   "良いですね。ただ自動デプロイは承認フローを挟む形にしてください。金融向けは本番モデルの変更に承認記録が必要になるケースがある。GitHubのProtected Branchのような仕組みをMLにも適用したい。"),
        msg("前田 彩",   "SHAP値の可視化を実装しました。「なぜこの融資がリスク高と判定されたか」を自然言語で説明するLLMレイヤーも追加。技術担当者向けには数値で、ビジネス担当者向けには文章で説明できる二層構造にしました。"),
        msg("山田 花奈", "モデルのドリフト検知も実装完了。学習データと推論データの分布を監視して、KL divergenceが閾値超えたら自動アラート。金融データは季節性があるので、誤検知を減らすためにウィンドウサイズを調整中です。"),
    ],
}


def section(title: str) -> None:
    print(f"\n{'=' * 55}\n{title}\n{'=' * 55}")


def create_or_get_channel(client: WebClient, name: str) -> str | None:
    """チャンネルを作成して channel_id を返す。失敗した場合は None を返す。"""
    try:
        resp = client.conversations_create(name=name, is_private=False)
        channel_id = resp["channel"]["id"]
        print(f"  作成済み: #{name} ({channel_id})")
        return channel_id
    except SlackApiError as e:
        err = e.response.get("error", "")
        if err == "name_taken":
            # 既存チャンネルを探す
            try:
                all_channels = []
                cursor = None
                while True:
                    r = client.conversations_list(
                        types="public_channel",
                        limit=200,
                        **({"cursor": cursor} if cursor else {}),
                    )
                    all_channels.extend(r["channels"])
                    cursor = r.get("response_metadata", {}).get("next_cursor")
                    if not cursor:
                        break
                for ch in all_channels:
                    if ch["name"] == name:
                        print(f"  既存チャンネル: #{name} ({ch['id']})")
                        return ch["id"]
            except SlackApiError:
                pass
            print(f"  WARN: #{name} は既存だが ID 取得失敗。スキップ。")
            return None
        elif err == "missing_scope":
            print(f"  WARN: channels:manage scope なし。#{name} の作成をスキップ。")
            return None
        else:
            print(f"  ERROR: #{name} 作成失敗: {e.response['error']}")
            return None


def post_messages(client: WebClient, channel_id: str, channel_name: str, messages: list[dict]) -> None:
    """メッセージをチャンネルに投稿する。"""
    for m in messages:
        if DRY_RUN:
            print(f"  [{m['speaker']}] {m['text'][:60]}{'...' if len(m['text']) > 60 else ''}")
            continue
        try:
            client.chat_postMessage(
                channel=channel_id,
                text=m["text"],
                username=m["speaker"],
                icon_emoji=m["emoji"],
            )
        except SlackApiError as e:
            err = e.response.get("error", "")
            if err == "missing_scope":
                # chat:write.customize なし → ペルソナ名をテキストに埋め込んでフォールバック
                try:
                    client.chat_postMessage(
                        channel=channel_id,
                        text=f"[{m['speaker']}] {m['text']}",
                    )
                except SlackApiError as e2:
                    print(f"  ERROR(fallback): {e2.response['error']} — {m['speaker']}")
                    continue
            elif err in ("not_in_channel", "channel_not_found"):
                # ボットをチャンネルに参加させてリトライ
                try:
                    client.conversations_join(channel=channel_id)
                    client.chat_postMessage(
                        channel=channel_id,
                        text=m["text"],
                        username=m["speaker"],
                        icon_emoji=m["emoji"],
                    )
                except SlackApiError as e2:
                    print(f"  ERROR(join+retry): {e2.response['error']} — {m['speaker']}")
                    continue
            else:
                print(f"  ERROR: {err} — {m['speaker']}")
                continue
        print(f"  OK [{m['speaker']}] {m['text'][:50]}...")
        time.sleep(0.5)  # レート制限対策


def main() -> None:
    load_dotenv()
    token = os.getenv("SLACK_BOT_OAUTH_TOKEN")
    if not token:
        print("ERROR: SLACK_BOT_OAUTH_TOKEN が .env に設定されていません。")
        sys.exit(1)

    client = WebClient(token=token)

    if DRY_RUN:
        print("=" * 55)
        print("DRY_RUN=True: 実際の投稿は行いません")
        print("=" * 55)

    # ---- STEP 1: プロジェクトチャンネルを作成/取得 ----
    section("STEP 1: プロジェクトチャンネル作成")
    project_channel_ids: dict[str, str] = {}
    for name in PROJECT_CHANNEL_NAMES:
        if DRY_RUN:
            print(f"  [DRY_RUN] #{name} を作成/取得します")
            project_channel_ids[name] = f"DRY_{name}"
        else:
            ch_id = create_or_get_channel(client, name)
            if ch_id:
                project_channel_ids[name] = ch_id

    # ---- STEP 2: 既存チャンネルへメッセージ投入 ----
    section("STEP 2: 既存チャンネルへメッセージ投入")
    for ch_name, ch_id in EXISTING_CHANNELS.items():
        if ch_name not in MESSAGES:
            continue
        msgs = MESSAGES[ch_name]
        print(f"\n  #{ch_name} ({len(msgs)} 件)")
        post_messages(client, ch_id, ch_name, msgs)

    # ---- STEP 3: プロジェクトチャンネルへメッセージ投入 ----
    section("STEP 3: プロジェクトチャンネルへメッセージ投入")
    for ch_name, ch_id in project_channel_ids.items():
        if ch_name not in MESSAGES:
            print(f"  SKIP: #{ch_name} のメッセージ定義なし")
            continue
        msgs = MESSAGES[ch_name]
        print(f"\n  #{ch_name} ({len(msgs)} 件)")
        if DRY_RUN:
            for m in msgs:
                print(f"    [{m['speaker']}] {m['text'][:60]}{'...' if len(m['text']) > 60 else ''}")
        else:
            post_messages(client, ch_id, ch_name, msgs)

    total = sum(len(v) for v in MESSAGES.values())
    section(f"完了: 合計 {total} 件のメッセージ{'プレビュー' if DRY_RUN else '投入'}完了")


if __name__ == "__main__":
    main()
