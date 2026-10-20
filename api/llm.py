"""言語モデル（LLM）を呼ぶ部分（コマ7・8。教員が用意したもの）

アプリ設定 LLM_PROVIDER で、呼び先を切り替える。
  mock        : モックLLM（既定）。OpenRouter を呼ばない。共有の利用上限を消費しない
  openrouter  : OpenRouter の本物のモデル。教員の合図があったときだけ使う

  stream_chat(messages)   応答の文字列を「少しずつ」返す（ジェネレーター。コマ7のアシスタント）
  complete_json(...)      応答をまとめて返す。JSON で答えさせるときに使う（コマ8の分類）
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
# 本物: OpenRouter（OpenAI 互換 API）
# ---------------------------------------------------------------------
def _openrouter_client():
    """呼ぶ前の確認をして、クライアントとモデルの ID を返す"""
    from openai import OpenAI

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
    return client, model


def _stream_openrouter(messages, max_tokens):
    from openai import APIConnectionError, APIStatusError, APITimeoutError

    client, model = _openrouter_client()
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


# =====================================================================
# JSON で答えさせる（コマ8）
# =====================================================================
def complete_json(messages, schema, mode, max_tokens):
    """messages を送り、応答の文字列（JSON のはず）をまとめて返す

    mode
      json_schema : JSON Schema を API の response_format で渡す（構造化出力に対応したモデル向け）
      prompt      : JSON Schema は渡さない（プロンプトの指示だけで JSON を出させる。非対応のモデル向け）
    どちらの場合も、返ってきた文字列が正しいかどうかは、呼ぶ側が必ず検証する。
    """
    if provider_name() == "openrouter":
        return _complete_json_openrouter(messages, schema, mode, max_tokens)
    return _complete_json_mock(messages, mode)


def _complete_json_openrouter(messages, schema, mode, max_tokens):
    from openai import APIConnectionError, APIStatusError, APITimeoutError

    client, model = _openrouter_client()
    options = {}
    if mode == "json_schema":
        options["response_format"] = {"type": "json_schema", "json_schema": schema}
        # 構造化出力に対応した提供元だけに送ってもらう（OpenRouter の機能）
        options["extra_body"] = {"provider": {"require_parameters": True}}
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0,  # 同じ入力には、なるべく同じ出力を返させる
            **options,
        )
    except APIStatusError as e:
        if e.status_code == 429:
            raise LLMError("利用上限に達した（429）。しばらく待つ") from e
        raise LLMError(f"モデルを呼べなかった（HTTP {e.status_code}）") from e
    except (APITimeoutError, APIConnectionError) as e:
        raise LLMError("モデルから時間内に応答がなかった") from e
    if not response.choices:
        raise LLMError("モデルの応答が空だった")
    return response.choices[0].message.content or ""


# 分類のモック: 問い合わせの文字列に含まれる言葉で、決まった結果を返す
_MOCK_RULES = [
    (("パスワード", "ロック", "アカウント", "ログイン"), "アカウント・パスワード"),
    (("VPN", "Wi-Fi", "無線", "ネットワーク", "つながらない"), "ネットワーク・VPN"),
    (("PC", "パソコン", "プリンター", "モニター", "キーボード"), "PC・機器"),
    (("給与", "有給", "休暇", "年末調整", "勤怠"), "人事・給与"),
    (("会議室", "備品", "鍵", "駐車", "郵便", "空調"), "総務・施設"),
]


def _complete_json_mock(messages, mode):
    """モックLLM（分類用）。アプリ設定 MOCK_FAULT で、わざと誤った出力を返せる

      MOCK_FAULT=none            : 正しい JSON を返す（既定）
      MOCK_FAULT=invalid_once    : 1回目だけ、決まりに合わない値を返す（再試行の練習）
      MOCK_FAULT=always_invalid  : 毎回、JSON ではない文を返す（諦めるときの練習）
    """
    fault = os.environ.get("MOCK_FAULT", "none")
    retried = any(m["role"] == "assistant" for m in messages)  # 再試行のときは、前の出力が入っている
    if fault == "always_invalid":
        return "分類しました。カテゴリはネットワーク関係で、急ぎだと思います。"
    if fault == "invalid_once" and not retried:
        return json.dumps(
            {"category": "ネットワーク", "priority": "緊急", "summary": "VPN に接続できない", "needs_human": False},
            ensure_ascii=False,
        )

    text = messages[-1]["content"] if not retried else messages[1]["content"]
    category = "その他"
    for words, name in _MOCK_RULES:
        if any(w in text for w in words):
            category = name
            break
    if any(w in text for w in ("急ぎではない", "いつでもよい")):
        priority = "低"
    elif any(w in text for w in ("至急", "止まって", "できない")):
        priority = "高"
    else:
        priority = "中"
    title = text.split("\n")[0].replace("件名:", "").strip()
    result = {
        "category": category,
        "priority": priority,
        "summary": f"（モック）{title}"[:60],
        "needs_human": category == "その他",
    }
    body = json.dumps(result, ensure_ascii=False)
    if mode == "prompt":
        # 構造化出力を使わないモデルがよくやる返し方（前置きの文と、コードブロック）をまねる
        return f"分類結果は次のとおりです。\n```json\n{body}\n```"
    return body
