"""api/resilience.py と api/llm_cache.py を確かめるテスト（コマ9）

実行のしかた（Codespace のターミナルで。Azure にも OpenRouter にもつながない）
  pip install pytest pydantic
  python -m pytest lesson09/test_resilience.py -v

モデルの代わりに、決まった順に「成功」や「429」を返す「偽物のモデル」（FakeModels）を使う。
待つ関数（sleep）も偽物にして、実際には待たずに「何秒待とうとしたか」だけを記録する。
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

import classification  # noqa: E402
import llm_cache  # noqa: E402
import resilience as r  # noqa: E402
from llm import LLMError, TransientLLMError  # noqa: E402

PRIMARY = "primary:free"
FALLBACK = "fallback:free"
OK = '{"category": "ネットワーク・VPN", "priority": "高", "summary": "VPN に接続できない", "needs_human": false}'


def rate_limited(retry_after=None):
    return TransientLLMError("429", 429, retry_after)


def unavailable():
    return TransientLLMError("503", 503, None)


class FakeModels:
    """モデルごとに、呼ばれたときに返すもの（文字列）か出す例外を、先頭から1つずつ使う"""

    def __init__(self, **script):
        self.script = {k.replace("_", ":"): list(v) for k, v in script.items()}
        self.calls = []

    def __call__(self, model):
        self.calls.append(model)
        outcome = self.script[model].pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeSleep:
    def __init__(self):
        self.waited = []

    def __call__(self, seconds):
        self.waited.append(seconds)


def run(models, budget=10, retries=2, max_wait=10, rand=lambda: 0.5):
    sleep = FakeSleep()
    result = r.call_with_resilience(
        models,
        [PRIMARY, FALLBACK],
        r.CallBudget(budget),
        max_retries_per_model=retries,
        base_delay=1,
        max_delay=8,
        max_wait=max_wait,
        sleep=sleep,
        rand=rand,
    )
    return result, sleep


# ---------------------------------------------------------------------
# 演習手順4: 待ち時間の計算
# ---------------------------------------------------------------------
def test_待ち時間は再試行のたびに倍になる():
    half = lambda: 0.5  # noqa: E731  ジッターの値を 0.5 に固定する
    delays = [r.backoff_delay(n, base=1, cap=100, rand=half) for n in (1, 2, 3, 4)]
    assert delays == [0.5, 1.0, 2.0, 4.0]


def test_待ち時間には上限がある():
    assert r.backoff_delay(10, base=1, cap=8, rand=lambda: 0.5) == 4.0


def test_ジッターで待ち時間がばらける():
    low = r.backoff_delay(3, base=1, cap=100, rand=lambda: 0.1)
    high = r.backoff_delay(3, base=1, cap=100, rand=lambda: 0.9)
    assert low == pytest.approx(0.4)
    assert high == pytest.approx(3.6)


def test_RetryAfterがあれば従う():
    assert r.backoff_delay(1, base=1, cap=8, retry_after=5, rand=lambda: 0.5) == 5


# ---------------------------------------------------------------------
# 演習手順5: 再試行とフォールバック
# ---------------------------------------------------------------------
def test_1回目で成功すれば待たない():
    models = FakeModels(primary_free=[OK])
    result, sleep = run(models)
    assert result.text == OK and result.model == PRIMARY
    assert sleep.waited == []


def test_429のあと指定の秒数だけ待って同じモデルで成功する():
    models = FakeModels(primary_free=[rate_limited(2), OK])
    result, sleep = run(models)
    assert models.calls == [PRIMARY, PRIMARY]
    assert sleep.waited == [2]
    assert result.model == PRIMARY


def test_主のモデルが失敗し続けたらフォールバックのモデルに移る():
    models = FakeModels(primary_free=[unavailable(), unavailable(), unavailable()], fallback_free=[OK])
    result, sleep = run(models)
    assert models.calls == [PRIMARY, PRIMARY, PRIMARY, FALLBACK]
    assert sleep.waited == [0.5, 1.0]  # 指数バックオフ（ジッター 0.5）
    assert result.model == FALLBACK


def test_長く待てと言われたら待たずに次のモデルへ():
    models = FakeModels(primary_free=[rate_limited(30)], fallback_free=[OK])
    result, sleep = run(models, max_wait=10)
    assert models.calls == [PRIMARY, FALLBACK]
    assert sleep.waited == []
    assert result.model == FALLBACK


def test_送り直しても直らない失敗はすぐに諦める():
    models = FakeModels(primary_free=[LLMError("401")], fallback_free=[OK])
    with pytest.raises(LLMError):
        run(models)
    assert models.calls == [PRIMARY]  # 再試行もフォールバックもしない


def test_呼ぶ回数の上限を超えない():
    models = FakeModels(primary_free=[rate_limited(1)] * 3, fallback_free=[rate_limited(1)] * 3)
    with pytest.raises(LLMError):
        run(models, budget=4)
    assert len(models.calls) == 4


def test_形式の再試行と通信の再試行で上限を分け合う():
    # 1回目: 429 → 2回目: 形式が誤り → 3回目: 429 → 上限（3回）
    bad = '{"category": "ネットワーク", "priority": "緊急", "summary": "x", "needs_human": false}'
    script = [rate_limited(1), bad, rate_limited(1), OK]
    budget = r.CallBudget(3)
    sleep = FakeSleep()

    def call_llm(messages):
        return r.call_with_resilience(
            lambda model: _pop(script), [PRIMARY], budget, 2, 1, 8, 10, sleep=sleep, rand=lambda: 0.5
        ).text

    inquiry = {"title": "VPN", "body": "VPN に接続できない"}
    with pytest.raises(LLMError):
        classification.classify(inquiry, call_llm, max_attempts=3)
    assert budget.used == 3


def _pop(script):
    outcome = script.pop(0)
    if isinstance(outcome, Exception):
        raise outcome
    return outcome


# ---------------------------------------------------------------------
# 演習手順6: キャッシュのキー
# ---------------------------------------------------------------------
MESSAGES = [
    {"role": "system", "content": "分類する係である"},
    {"role": "user", "content": "件名: VPN\n本文: VPN に接続できない"},
]
SCHEMA = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}


def key(**changes):
    args = {"purpose": "classify", "model": PRIMARY, "messages": MESSAGES, "schema": SCHEMA, "mode": "json_schema"}
    args.update(changes)
    return llm_cache.cache_key(**args)


def test_同じ入力なら同じキーになる():
    assert key() == key()
    assert len(key()) == 64 and all(ch in "0123456789abcdef" for ch in key())


def test_問い合わせが違えば別のキーになる():
    other = [MESSAGES[0], {"role": "user", "content": "件名: パスワード\n本文: ログインできない"}]
    assert key() != key(messages=other)


def test_プロンプトが違えば別のキーになる():
    other = [{"role": "system", "content": "別の指示"}, MESSAGES[1]]
    assert key() != key(messages=other)


def test_モデル・スキーマ・方式が違えば別のキーになる():
    assert key() != key(model=FALLBACK)
    assert key() != key(schema={**SCHEMA, "required": []})
    assert key() != key(mode="prompt")


def test_スキーマの項目の順序が違っても同じキーになる():
    reordered = json.loads('{"required": ["a"], "properties": {"a": {"type": "string"}}, "type": "object"}')
    assert key() == key(schema=reordered)


def test_キーに問い合わせの本文が入っていない():
    assert "VPN" not in key()
