"""OpenRouter の OpenAI 互換 API を「1回だけ」呼んで確かめるスクリプト（コマ5）

使い方
  python lesson05/openrouter_check.py --dry-run   送る内容を表示するだけ（API は呼ばない）
  python lesson05/openrouter_check.py             本物を1回だけ呼ぶ（教員の合図があったときだけ）

- キーは環境変数 OPENROUTER_API_KEY から読む（Codespaces のシークレットで渡す）。キーの値は表示しない。
- モデルは lesson05/config.json で指定する。ID の末尾が ":free" のモデル（無料モデル）以外は呼ばない。
- 失敗しても自動で再試行しない（再試行は共有の利用上限を消費する。再試行の設計はコマ9で扱う）。
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

BASE_URL = "https://openrouter.ai/api/v1"
CONFIG_PATH = Path(__file__).with_name("config.json")
PLACEHOLDER = "set-by-teacher/model-name:free"


def load_model():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    model = config["chat_model"]
    if model == PLACEHOLDER:
        sys.exit("モデルがまだ指定されていない。教員の指示を待つこと。")
    if not model.endswith(":free"):
        sys.exit(f"無料モデル（ID の末尾が :free）以外は呼ばない: {model}")
    return model


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="送らずに、送る内容だけを表示する")
    args = parser.parse_args()

    request = {
        "model": load_model(),
        "messages": [
            {"role": "system", "content": "あなたは日本語で簡潔に答えるアシスタントである。"},
            {"role": "user", "content": "RAG とは何かを1文で説明してください。"},
        ],
        "max_tokens": 300,
    }

    if args.dry_run:
        print("送信先:", BASE_URL + "/chat/completions")
        print("送る内容（JSON）:")
        print(json.dumps(request, ensure_ascii=False, indent=2))
        print("（--dry-run なので送っていない）")
        return

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        sys.exit("環境変数 OPENROUTER_API_KEY がない。Codespaces のシークレットを登録し、Codespace を再起動する。")

    from openai import APIStatusError, APITimeoutError, OpenAI

    client = OpenAI(base_url=BASE_URL, api_key=api_key, timeout=60, max_retries=0)

    started = time.monotonic()
    try:
        response = client.chat.completions.create(**request)
    except APIStatusError as e:
        print(f"エラー: HTTP {e.status_code}")
        if e.status_code == 429:
            print("利用上限に達した（429）。再実行せず、教員の指示を待つ。")
        return
    except APITimeoutError:
        print("時間内に応答がなかった（タイムアウト）。再実行せず、教員の指示を待つ。")
        return
    elapsed = time.monotonic() - started

    content = response.choices[0].message.content
    print("応答:", content if content else "（本文が空だった）")
    print("応答したモデル:", response.model)
    print(f"所要時間: {elapsed:.1f} 秒")
    if response.usage:
        print("トークン数: 入力", response.usage.prompt_tokens, "／ 出力", response.usage.completion_tokens)


if __name__ == "__main__":
    main()
