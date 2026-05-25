"""Slack デモデータ追加投入スクリプト (v2).

新規追加:
  - tweet_nakamura: 中村 大樹の個人vlog（Kaggle実績ツイート含む・8件）
  - tweet_yamada:   山田 花奈の個人vlog（MLOps・自動化ツイート・8件）
  - proj-ec-recommend: EC推薦エンジンPJのチャンネル（10件）

前提条件:
  - SLACK_BOT_OAUTH_TOKEN が .env に設定されていること
  - chat:write / chat:write.customize スコープが有効であること

実行:
  uv run python scripts/seed_slack_demo_v2.py
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

# ---- ペルソナ設定 ----
PERSONA = {
    "中村 大樹": ":chart_with_upwards_trend:",
    "山田 花奈": ":gear:",
    "田中 誠":   ":briefcase:",
    "前田 彩":   ":brain:",
}

NEW_CHANNEL_NAMES = [
    "tweet_nakamura",
    "tweet_yamada",
    "tweet_tanaka",
    "proj-ec-recommend",
    "proj-medical-imaging-ai",
]


def msg(speaker: str, text: str) -> dict:
    return {"speaker": speaker, "emoji": PERSONA[speaker], "text": text}


# ============================================================
# メッセージ定義
# ============================================================
MESSAGES: dict[str, list[dict]] = {

    # ----------------------------------------------------------
    # tweet_nakamura — 中村 大樹の個人vlog
    # Kaggle銀メダル×2 + リーダー適性成長のストーリー
    # ----------------------------------------------------------
    "tweet_nakamura": [
        msg("中村 大樹",
            "ECレコメンドのデータ探索が終わった。購買ログ10GBを前処理して特徴量を70種類設計。"
            "LightGBMが協調フィルタリングより明らかに強い。ロングテール商品の精度が段違い。"
            "Recall@10が0.34→0.51になった。この差は大きい。"),
        msg("中村 大樹",
            "Kaggle始めてみた。SIIM-ISIC Melanoma Classification（皮膚がん分類）。"
            "画像系コンペは初挑戦。MLとは別の難しさがある。"
            "データ拡張の戦略が全然分からなくて苦労している。"),
        msg("中村 大樹",
            "画像コンペのデータ拡張、やっと整理できてきた。TTA（Test Time Augmentation）と"
            "MixUpを組み合わせる戦略が効く。外部データセット（ISIC 2019）を追加したらLBスコアが大幅改善。"
            "コンペは自分の知識の境界線を教えてくれる場所だと思う。"),
        msg("中村 大樹",
            "🥈 Kaggle 銀メダル取れた！！ SIIM-ISIC Melanoma Classification。"
            "EfficientNet-B5 + ViT のアンサンブルが最終的な勝ち筋だった。"
            "1位との差は0.004。悔しいけど嬉しい。画像系おもしろすぎる。続けよう。"),
        msg("中村 大樹",
            "Vision Transformer (ViT) の論文を読み直した。Attention Mapの可視化が"
            "医療画像に特に有用そう。「どこを見て判断したか」が分かることが医療AIにとって重要。"
            "業務でも画像AIを使う機会があれば積極的にやりたい。"),
        msg("中村 大樹",
            "RSNA Pneumonia Detection（胸部X線画像から肺炎検出）のコンペに参加。"
            "医療画像特有の前処理（WINDOWINGとか）が難しい。"
            "pydicomでDICOMファイルを扱う必要があって初めて触った。勉強になる。"),
        msg("中村 大樹",
            "🥈 Kaggle 銀メダル2枚目！ RSNA Pneumonia Detection。"
            "Swin Transformerが効いた。局所・大局パターンを同時に捉えられる。"
            "医療画像 × Vision Transformerの組み合わせ、本当に強い。"
            "これをプロダクトに活かせる仕事をしたい。"),
        msg("中村 大樹",
            "ECプロジェクトの最終レビューが終わった。CTR 23%改善で目標達成。"
            "田中さんから「次のPJでテックリードをやってほしい」と言ってもらえた。"
            "正直まだ自信ないけど、画像AI系のPJならKaggleで培った知識が活かせると思う。"
            "リードとして設計から推進まで一回やってみたい。"),
    ],

    # ----------------------------------------------------------
    # tweet_yamada — 山田 花奈の個人vlog
    # MLOps・インフラ自動化のストーリー
    # ----------------------------------------------------------
    "tweet_yamada": [
        msg("山田 花奈",
            "Azure ML Pipelineでモデル学習〜評価〜デプロイを全自動化できた。"
            "毎朝6時に最新データで再学習が走って、精度が閾値を超えればAzure Container Appsに自動デプロイ。"
            "インフラとMLを繋げられるのがMLOpsの醍醐味だと思う。"),
        msg("山田 花奈",
            "GitHub Actionsのビルド時間を12分→4分30秒に短縮。"
            "ジョブ並列化とDockerのレイヤーキャッシュ最適化が効いた。"
            "開発者体験の改善は地味だけど大事。毎日使うものだから積み重なる。"),
        msg("山田 花奈",
            "モデルドリフト検知を実装した。学習データと推論データの分布を監視して"
            "KL divergenceが閾値超えたら自動アラート。"
            "ECのレコメンドエンジンは季節性があるから、ウィンドウサイズを90日に設定して誤検知を抑えた。"),
        msg("山田 花奈",
            "DockerfileのマルチステージビルドでMLの推論イメージを1.2GB→380MBに削減。"
            "python:3.12-slim + 必要な依存のみに絞ったら起動時間も半分になった。"
            "コンテナサイズってAzure Container Appsのコスト直結するから真剣に向き合う必要がある。"),
        msg("山田 花奈",
            "「MLOpsエンジニアとDevOpsエンジニアの違いは何か」ってよく聞かれる。"
            "私の答えは「モデルのライフサイクル管理まで責任を持つかどうか」。"
            "モデルのバージョン管理、実験追跡、本番監視——これらをCIと統合できるのが本当のMLOps。"),
        msg("山田 花奈",
            "A/Bテスト基盤の設計で悩んでいる。トラフィック分割をNginxでやるか"
            "Azure API Managementでやるか。後者はコストがかかるけど管理が楽。"
            "中村さんのモデルのA/Bをやるためだから、手動ミスが出ないほうを選ぼうと思う。"),
        msg("山田 花奈",
            "Kubernetesのオートスケーリング設定を最適化した。"
            "推論APIのp99レイテンシが200ms→95msに改善。"
            "HPA（Horizontal Pod Autoscaler）とVPA（Vertical）を組み合わせるのがポイント。"
            "負荷試験で十分に検証してから本番に適用するようにしている。"),
        msg("山田 花奈",
            "MLOpsの仕事、最初は「インフラの人」として見られることが多かった。"
            "でも今はモデルの品質管理まで一緒に考えるようになった。"
            "中村さんとの協働でML側の視点を学べた。インフラとMLを繋ぐ人材として"
            "これからも成長していきたい。"),
    ],

    # ----------------------------------------------------------
    # proj-ec-recommend — EC推薦エンジンPJのチャンネル
    # 中村の成長・提案力の変化が見えるチャンネル
    # ----------------------------------------------------------
    "proj-ec-recommend": [
        msg("田中 誠",
            "【EC推薦エンジンPJ始動】今スプリントの方針です。"
            "中村さんはデータ探索とMLモデルのベースライン構築を優先してください。"
            "山田さんはAzure MLのパイプライン設計と並行して進めてもらえると助かります。"
            "困ったことは即スレッドに書いてください。"),
        msg("中村 大樹",
            "EDAレポートできました。購買データの基本統計と欠損の分布を確認しました。"
            "気になった点：人気商品TOP100が全購買の67%を占めていて、"
            "協調フィルタリングだとロングテール商品の推薦が難しそうです。"
            "LightGBMで商品特徴量を入れる方向を試してみていいですか？"),
        msg("田中 誠",
            "中村さん、EDAお疲れ様です。LightGBMの提案、試してみてください。"
            "ロングテール問題はECではよくある課題なので、"
            "解決できれば差別化ポイントになります。"),
        msg("山田 花奈",
            "Azure MLのパイプライン設計、ドラフトできました。"
            "学習→評価→条件付きデプロイの3ステップ構成です。"
            "中村さんのローカルコードをそのままDockerコンテナ化して取り込めます。"
            "準備できたら共有します。"),
        msg("中村 大樹",
            "LightGBMの最初の実験結果が出ました。"
            "Recall@10: 協調フィルタリング 0.34 → LightGBM 0.51。大幅改善です。"
            "さらに2つの特徴量追加を検討しています。"
            "①ユーザーの直近30日の閲覧カテゴリ分布 ②商品の同カテゴリ内売れ筋ランク。"
            "先週、両方実験した結果、①の方が効果が高かったです。採用しようと思います。"),
        msg("田中 誠",
            "中村さん、実験結果と根拠がセットで提案できてていいですね。"
            "採用します。山田さん、パイプラインへの組み込みをお願いします。"),
        msg("山田 花奈",
            "中村さんのコード、パイプラインに組み込み完了しました！"
            "今朝から自動学習が走っています。モデルレジストリで"
            "バージョン管理も自動です。精度ログをダッシュボードに載せました。"),
        msg("中村 大樹",
            "アンサンブルモデルのA/Bテスト結果が出ました。"
            "コントロール群 vs テスト群で クリック率 +23%。目標の+20%を達成しました！"
            "Recall@10も最終的に0.67まで到達。"
            "山田さんの自動再学習の仕組みが効いて、6月に入ってから更に精度が上がりました。"),
        msg("山田 花奈",
            "目標達成おめでとうございます！"
            "中村さんのモデルの品質が高かったから維持・改善できました。"
            "本番デプロイの最終確認、今週中にやります。"),
        msg("田中 誠",
            "【PJ完了報告】CTR +23%、Recall@10=0.67でプロジェクト目標達成です。"
            "中村さん・山田さん、6ヶ月間お疲れ様でした。"
            "中村さんはML設計からプロジェクト進行管理まで一人でやり切れるようになった。"
            "次のプロジェクトでテックリードとして力を発揮してもらいます。"),
    ],

    # ----------------------------------------------------------
    # tweet_tanaka — 田中 誠のマネジメントvlog
    # メンバー育成・中村の成長観察・PJ-C展望
    # ----------------------------------------------------------
    "tweet_tanaka": [
        msg("田中 誠",
            "1on1で中村さんと話した。Kaggleで画像系コンペに本気で取り組んでいるという。"
            "業務のMLとは別に自発的に学んでいる。"
            "こういう人材をいかに活かすかが、TLとしての自分の仕事だと思う。"),
        msg("田中 誠",
            "中村さんの最近の提案が変わってきた。以前は「やってみたいです」レベルだったのが、"
            "「先週の検証で①と②を比べると①が有効でした、なぜならば〜」という形になった。"
            "根拠データを持って話せるエンジニアになっている。成長が速い。"),
        msg("田中 誠",
            "中村さんがKaggle銀メダルを取ったと報告してくれた。しかも医療画像系。"
            "業務外でここまで自発的に学べる人材は本当に貴重だ。"
            "この経験を業務で活かせる場を、次のPJで作ろうと思う。"),
        msg("田中 誠",
            "EC推薦エンジンPJ、無事完了。中村さんは最終レビューを自分でリードしてくれた。"
            "ML設計・実験・プロジェクト進行まで一人でやり切れるようになった。"
            "次のPJでテックリードを正式に打診した。本人は少し戸惑っていたが、絶対にできると思う。"),
        msg("田中 誠",
            "医療画像AI診断支援システムの新PJが計画段階に入った。"
            "画像認識×医療×Azure。技術難度は今まで最高クラス。"
            "中村さんの成長軌跡とKaggleの実績を見ると、テックリードを任せるべき人材だと確信している。"
            "アサインはエージェントにも分析させてみる予定。"),
    ],

    # ----------------------------------------------------------
    # proj-medical-imaging-ai — 医療画像AI診断支援PJ（PJ-C）
    # 計画段階・アサイン待ち
    # ----------------------------------------------------------
    "proj-medical-imaging-ai": [
        msg("田中 誠",
            "【PJ-C準備開始】医療画像AI診断支援システムのキックオフ準備を始めます。"
            "期間: 2026-08-01〜2026-11-30。"
            "必要スキル: Python, 画像認識, CNN/ViT, PyTorch, Azure, DICOM処理。"
            "チームアサインはTalentScopeエージェントに分析・提案してもらいます。"),
        msg("田中 誠",
            "このPJの最大の課題はテックリード選定。"
            "医療画像×DL×Azureデプロイまで一気通貫で引っ張れる人材が必要。"
            "社内でこのスキルセットを持つ人材の特定と、成長可能性の評価を進めている。"),
        msg("田中 誠",
            "PJ-Cのメンバー選定中。8月開始に向けてアサイン計画を立案中。"
            "詳細はNotion PJ-Cページ参照。メンバーが確定次第このチャンネルで共有します。"
            "アサイン提案をAIエージェントに依頼予定。結果をここに貼ります。"),
    ],
}


def section(title: str) -> None:
    print(f"\n{'=' * 55}\n{title}\n{'=' * 55}")


def create_or_get_channel(client: WebClient, name: str) -> str | None:
    try:
        resp = client.conversations_create(name=name, is_private=False)
        ch_id = resp["channel"]["id"]
        print(f"  作成済み: #{name} ({ch_id})")
        return ch_id
    except SlackApiError as e:
        err = e.response.get("error", "")
        if err == "name_taken":
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
            print(f"  ERROR: #{name} 作成失敗: {err}")
            return None


def post_messages(client: WebClient, channel_id: str, messages: list[dict]) -> None:
    for m in messages:
        if DRY_RUN:
            print(f"  [{m['speaker']}] {m['text'][:70]}{'...' if len(m['text']) > 70 else ''}")
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
                try:
                    client.chat_postMessage(
                        channel=channel_id,
                        text=f"[{m['speaker']}] {m['text']}",
                    )
                except SlackApiError as e2:
                    print(f"  ERROR(fallback): {e2.response['error']} — {m['speaker']}")
                    continue
            elif err in ("not_in_channel", "channel_not_found"):
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
        time.sleep(0.5)


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

    section("STEP 1: 新規チャンネル作成")
    channel_ids: dict[str, str] = {}
    for name in NEW_CHANNEL_NAMES:
        if DRY_RUN:
            print(f"  [DRY_RUN] #{name} を作成/取得します")
            channel_ids[name] = f"DRY_{name}"
        else:
            ch_id = create_or_get_channel(client, name)
            if ch_id:
                channel_ids[name] = ch_id

    section("STEP 2: メッセージ投入")
    for ch_name, ch_id in channel_ids.items():
        if ch_name not in MESSAGES:
            print(f"  SKIP: #{ch_name} のメッセージ定義なし")
            continue
        msgs = MESSAGES[ch_name]
        print(f"\n  #{ch_name} ({len(msgs)} 件)")
        if DRY_RUN:
            for m in msgs:
                print(f"    [{m['speaker']}] {m['text'][:70]}{'...' if len(m['text']) > 70 else ''}")
        else:
            post_messages(client, ch_id, msgs)

    total = sum(len(v) for v in MESSAGES.values())
    section(f"完了: 合計 {total} 件のメッセージ{'プレビュー' if DRY_RUN else '投入'}完了")
    print("  data-schema.md の Slack チャンネル構成に以下を追記してください:")
    print("    tweet_nakamura | nakamura@abc.com")
    print("    tweet_yamada   | yamada@abc.com")
    print("    proj-ec-recommend | 大手EC向けレコメンドエンジン開発")


if __name__ == "__main__":
    main()
