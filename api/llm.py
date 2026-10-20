"""言語モデル（LLM）を呼ぶ部分（コマ7。教員が用意したもの）

アプリ設定 LLM_PROVIDER で、呼び先を切り替える。
  mock        : モックLLM（既定）。OpenRouter を呼ばない。共有の利用上限を消費しない
  openrouter  : OpenRouter の本物のモデル。教員の合図があったときだけ使う

どちらも stream_chat(messages) で、応答の文字列を「少しずつ」返す（ジェネレーター）。
呼ぶ側（function_app.py）は、どちらが動いているかを気にしなくてよい。
（呼び先を差し替えられるようにする設計は、コマ9で詳しく扱う）
"""

import json
import os
import time
from pathlib import Path

CONFIG_PATH = Path(__file__).with_name("llm_config.json")
PLACEHOLDER_MODEL = "set-by-teacher/model-name:free"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class LLMError(Exception):
    """LLM を呼べなかった・途中で失敗したことを表す（利用者に見せてよい文だけを入れる）"""


def load_config():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def provider_name():
    return os.environ.get("LLM_PROVIDER", "mock")


def stream_chat(messages, max_tokens):
    """messages を送り、応答の文字列を少しずつ返す"""
    if provider_name() == "openrouter":
        yield from _stream_openrouter(messages, max_tokens)
    else:
        yield from _stream_mock(messages)


# ---------------------------------------------------------------------
# モックLLM: 受け取った messages の様子を、そのまま文章にして少しずつ返す
#   本物の代わりに、「何件・どれくらいの量を送ったか」を確かめるのに使う
# ---------------------------------------------------------------------
def _stream_mock(messages):
    last = messages[-1]["content"]
    roles = [m["role"] for m in messages]
    chars = sum(len(m["content"]) for m in messages)
    text = (
        "（モックLLMの応答）"
        f"受け取ったメッセージは {len(messages)} 件"
        f"（system {roles.count('system')}・user {roles.count('user')}・"
        f"assistant {roles.count('assistant')}）、合計 {chars} 文字だった。"
        f"最後の質問の先頭は「{last[:20]}」である。"
    )
    for i in range(0, len(text), 4):
        time.sleep(0.08)  # 本物のように少しずつ届くことを再現する
        yield text[i : i + 4]


# ---------------------------------------------------------------------
# 本物: OpenRouter（OpenAI 互換 API）をストリーミングで呼ぶ
# ---------------------------------------------------------------------
def _stream_openrouter(messages, max_tokens):
    from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

    model = load_config()["chat_model"]
    if model == PLACEHOLDER_MODEL:
        raise LLMError("モデルが指定されていない（教員の指示を待つ）")
    if not model.endswith(":free"):
        # 許可するモデルは無料モデルだけ。誤って有料モデルを指定しても呼ばない
        raise LLMError("無料モデル以外は呼ばない設定になっている")

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key.startswith("sk-or-"):
        raise LLMError("OpenRouter のキーが届いていない（Key Vault を確かめる）")

    # max_retries=0: ライブラリの自動の再試行を止める（共有の利用上限を消費するため。コマ9で扱う）
    client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=api_key, timeout=60, max_retries=0)
    try:
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,  # 出力の長さの上限
            stream=True,
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            if choice.finish_reason == "error":
                # 途中で失敗した（HTTP の状態は 200 のまま、イベントとして届く）
                raise LLMError("モデルの応答が途中で失敗した")
            if choice.delta and choice.delta.content:
                yield choice.delta.content
    except APIStatusError as e:
        if e.status_code == 429:
            raise LLMError("利用上限に達した（429）。しばらく待つ") from e
        raise LLMError(f"モデルを呼べなかった（HTTP {e.status_code}）") from e
    except (APITimeoutError, APIConnectionError) as e:
        raise LLMError("モデルから時間内に応答がなかった") from e
