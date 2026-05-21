"""Azure OpenAI 接続検証スクリプト（フェーズ1）.

段階的に Azure OpenAI を叩き、各ステップの結果を標準出力に表示する。
  1. .env から AZURE_OPENAI_* を読み込む
  2. AzureOpenAI クライアントで chat completion を呼び出す
  3. レスポンスの内容を表示して疎通確認
"""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from openai import AzureOpenAI


def section(title: str) -> None:
    print(f"\n{'=' * 50}\n{title}\n{'=' * 50}")


def main() -> int:
    section("STEP 1: .env 読み込み")
    load_dotenv()
    api_key    = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint   = os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

    missing = [k for k, v in {
        "AZURE_OPENAI_API_KEY": api_key,
        "AZURE_OPENAI_ENDPOINT": endpoint,
        "AZURE_OPENAI_DEPLOYMENT_NAME": deployment,
    }.items() if not v]
    if missing:
        print(f"NG: 以下のキーが .env に見つかりません: {missing}")
        return 1
    print(f"OK: キー取得 / endpoint={endpoint} / deployment={deployment}")

    section("STEP 2: AzureOpenAI クライアント作成")
    try:
        client = AzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version="2024-02-01",
        )
        print("OK: クライアント作成成功")
    except Exception as e:
        print(f"NG: クライアント作成失敗 ({e})")
        return 1

    section("STEP 3: Chat Completion 疎通確認")
    try:
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": "あなたは人事エージェントTalentScopeです。"},
                {"role": "user",   "content": "こんにちは。一言で自己紹介してください。"},
            ],
            max_tokens=100,
        )
        reply = response.choices[0].message.content
        usage = response.usage
        print(f"OK: レスポンス取得")
        print(f"    モデル    : {response.model}")
        print(f"    応答内容  : {reply}")
        print(f"    トークン  : prompt={usage.prompt_tokens} / completion={usage.completion_tokens}")
    except Exception as e:
        print(f"NG: Chat Completion 失敗 ({e})")
        return 1

    section("検証完了: Azure OpenAI 接続 OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
